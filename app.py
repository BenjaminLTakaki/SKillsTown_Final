import os
import json
import re
from dotenv import load_dotenv
import sys
import traceback
import PyPDF2
import requests
from datetime import datetime 
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, current_app, Response, send_from_directory
from flask_login import login_required, current_user, LoginManager, login_user, logout_user, UserMixin
from werkzeug.utils import secure_filename
from sqlalchemy import text
from jinja2 import ChoiceLoader, FileSystemLoader
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
import threading
import time
import schedule

load_dotenv()

try:
    from auto_migration import run_auto_migration
except ImportError:
    def run_auto_migration():
        print("Auto migration script not found")
        return True
    
try:
    from local_config import NARRETEX_API_URL, check_environment, LOCAL_DATABASE_URL, DEVELOPMENT_MODE
except ImportError:
    # Production environment - local_config.py doesn't exist
    DEVELOPMENT_MODE = False
    LOCAL_DATABASE_URL = None
    check_environment = None
    
    # Get from environment variables instead
    NARRETEX_API_URL = os.environ.get('NARRETEX_API_URL', 'https://narretex-app.onrender.com')

# Override DEVELOPMENT_MODE for production detection
DEVELOPMENT_MODE = DEVELOPMENT_MODE and not (
    os.environ.get('RENDER') or 
    os.environ.get('DATABASE_URL', '').startswith('postgres') or
    os.environ.get('FLASK_ENV') == 'production'
)

def is_production():
    return (
        os.environ.get('RENDER') or 
        os.environ.get('DATABASE_URL', '').startswith('postgres') or
        os.environ.get('FLASK_ENV') == 'production'
    )

# API configurations
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1/models/gemini-2.0-flash:generateContent"
QUIZ_API_BASE_URL = os.environ.get('QUIZ_API_BASE_URL', 'https://chisel-app.onrender.com')
QUIZ_API_ACCESS_TOKEN = os.environ.get('QUIZ_API_ACCESS_TOKEN', '')

def get_url_for(*args, **kwargs):
    url = url_for(*args, **kwargs)
    return url

# Import models after db is defined
from models import Company, Student, Category, ContentPage, Course, CourseContentPage, UserProfile, SkillsTownCourse, CourseDetail, CourseQuiz, CourseQuizAttempt, UserCourse, UserLearningProgress, db

def get_quiz_api_headers():
    return {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {QUIZ_API_ACCESS_TOKEN}'
    }

# Self-pinging service to keep Render instances alive
class SelfPingService:
    def __init__(self, app_url, quiz_api_url, narretex_url, qdrant_url):
        self.app_url = app_url
        self.quiz_api_url = quiz_api_url
        self.narretex_url = narretex_url
        self.qdrant_url = qdrant_url
        self.running = False
        
    def ping_service(self, url, service_name):
        try:
            # Use health check endpoints when available
            health_endpoints = ['/health', '/', '/status']
            
            for endpoint in health_endpoints:
                try:
                    full_url = f"{url}{endpoint}"
                    response = requests.get(full_url, timeout=30)
                    if response.status_code == 200:
                        print(f"✅ {service_name} ping successful: {full_url}")
                        return True
                except:
                    continue
            
            print(f"⚠️ {service_name} ping failed: {url}")
            return False
            
        except Exception as e:
            print(f"❌ Error pinging {service_name}: {e}")
            return False
    
    def ping_all_services(self):
        """Ping all services to keep them alive"""
        print(f"🔄 Pinging services at {datetime.now()}")
        
        services = [
            (self.app_url, "SkillsTown App"),
            (self.quiz_api_url, "Quiz API"),
            (self.narretex_url, "NarreteX API"),
            (self.qdrant_url, "Qdrant DB")
        ]
        
        for url, name in services:
            if url:
                self.ping_service(url, name)
    
    def start_pinging(self):
        """Start the pinging service in a separate thread"""
        if self.running:
            return
            
        self.running = True
        
        # Schedule pings every 12 minutes (well below 15-minute timeout)
        schedule.every(12).minutes.do(self.ping_all_services)
        
        def run_scheduler():
            while self.running:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
        
        # Start in daemon thread so it doesn't prevent app shutdown
        ping_thread = threading.Thread(target=run_scheduler, daemon=True)
        ping_thread.start()
        
        print("🚀 Self-pinging service started - pinging every 12 minutes")
        
        # Do initial ping after 2 minutes
        initial_ping_thread = threading.Thread(
            target=lambda: (time.sleep(120), self.ping_all_services()), 
            daemon=True
        )
        initial_ping_thread.start()
    
    def stop_pinging(self):
        """Stop the pinging service"""
        self.running = False
        print("🛑 Self-pinging service stopped")

# Global ping service
ping_service = None

def generate_podcast_for_course(course_name, course_description):
    """
    Generate a podcast for a specific course using NarreteX API
    Uses the detailed course catalog for rich content
    """
    try:
        # Load the course catalog to get detailed information
        course_details = get_detailed_course_info(course_name)
        
        # Create comprehensive content from catalog data
        document_content = f"""
        COURSE: {course_name}
        
        DESCRIPTION: {course_description}
        
        DETAILED COURSE INFORMATION:
        {format_course_details(course_details)}
        
        EDUCATIONAL CONTEXT:
        This course is designed to provide comprehensive knowledge and practical skills.
        Students will gain hands-on experience through real-world projects and exercises.
        The curriculum follows industry best practices and includes the latest technologies and methodologies.
        """
        
        # Debug: Print the content being sent
        print("=" * 50)
        print("DEBUG: Course catalog content:")
        print(f"Length: {len(document_content)} characters")
        print("Content preview:")
        print(document_content[:300] + "...")
        print("=" * 50)
        
        # Prepare payload
        payload = {
            "topic": course_name,
            "document": document_content
        }
        print(f"DEBUG: Sending payload to NarreteX: {json.dumps(payload, indent=2)}")

        # Add retry logic for Render's cold start issues
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Call NarreteX instant podcast API
                response = requests.post(
                    f"{NARRETEX_API_URL}/instant-podcast",
                    json=payload, # Use the payload variable
                    timeout=180,  # Increased timeout for Render
                    headers={
                        'Content-Type': 'application/json',
                        'User-Agent': 'SkillsTown/1.0'
                    }
                )
                
                if response.status_code == 200:
                    print(f"✅ Podcast generated successfully on attempt {attempt + 1}")
                    return response.content
                elif response.status_code == 503:
                    # Service temporarily unavailable, likely cold start
                    print(f"⏳ Service cold start detected, attempt {attempt + 1}/{max_retries}")
                    if attempt < max_retries - 1:
                        time.sleep(10 * (attempt + 1))  # Exponential backoff
                        continue
                else:
                    print(f"❌ Podcast generation failed: {response.status_code}")
                    print(f"Response: {response.text}")
                    break
                    
            except requests.exceptions.Timeout:
                print(f"⏰ Request timeout on attempt {attempt + 1}/{max_retries}")
                if attempt < max_retries - 1:
                    time.sleep(5 * (attempt + 1))
                    continue
            except requests.exceptions.ConnectionError:
                print(f"🔌 Connection error on attempt {attempt + 1}/{max_retries}")
                if attempt < max_retries - 1:
                    time.sleep(5 * (attempt + 1))
                    continue
        
        print("❌ All podcast generation attempts failed")
        return None
            
    except Exception as e:
        print(f"❌ Error generating podcast: {e}")
        traceback.print_exc()
        return None

def get_detailed_course_info(course_name):
    """
    Get detailed course information from the course catalog
    """
    try:
        catalog_path = os.path.join(os.path.dirname(__file__), 'static', 'data', 'course_catalog.json')
        with open(catalog_path, 'r', encoding='utf-8') as f:
            catalog = json.load(f)
        
        # Search for the course in the catalog
        for category in catalog.get('categories', []):
            for course in category.get('courses', []):
                if course['name'].lower() == course_name.lower():
                    return course
        
        # If not found, return minimal info
        return {"name": course_name, "description": "Course information not available"}
        
    except Exception as e:
        print(f"Error loading course catalog: {e}")
        return {"name": course_name, "description": "Course information not available"}

def format_course_details(course_details):
    """
    Format course details into a comprehensive text description
    """
    if not course_details:
        return "Course details not available."
    
    formatted = f"Course: {course_details.get('name', 'Unknown')}\n\n"
    formatted += f"Description: {course_details.get('description', 'No description available')}\n\n"
    
    if 'duration' in course_details:
        formatted += f"Duration: {course_details['duration']}\n"
    
    if 'level' in course_details:
        formatted += f"Level: {course_details['level']}\n\n"
    
    if 'skills' in course_details and course_details['skills']:
        formatted += "Skills You'll Learn:\n"
        for skill in course_details['skills']:
            formatted += f"- {skill}\n"
        formatted += "\n"
    
    if 'projects' in course_details and course_details['projects']:
        formatted += "Projects You'll Build:\n"
        for project in course_details['projects']:
            formatted += f"- {project}\n"
        formatted += "\n"
    
    if 'career_paths' in course_details and course_details['career_paths']:
        formatted += "Career Opportunities:\n"
        for career in course_details['career_paths']:
            formatted += f"- {career}\n"
        formatted += "\n"
    
    return formatted

# Auth setup
def init_auth(app, get_url_for_func, get_stats_func):
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'login'
    
    @login_manager.user_loader
    def load_user(user_id):
        return Student.query.get(user_id)
    
    return db

def init_database():
    """Initialize database with migrations"""
    try:
        # Run auto-migration first
        if is_production():
            print("🔧 Running production database migration...")
            run_auto_migration()
        
        # Then create all tables (this is safe - won't recreate existing tables)
        db.create_all()
        print("✅ Database initialization complete")
        
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        # Don't fail the app startup, just log the error
        import traceback
        traceback.print_exc()

# Helper function to serialize learning progress
def serialize_learning_progress(progress):
    """Converts UserLearningProgress object to a JSON-serializable dict."""
    if not progress:
        print("DEBUG: Serialize Progress: Received None for progress object.")
        return None
    
    serialized_data = {
        'id': None, 'user_id': None, 'course_id': None,
        'knowledge_areas': {}, 'weak_areas': [], 'strong_areas': [],
        'recommended_topics': [], 'learning_curve': [],
        'overall_progress': 0, 'mastery_level': 'beginner',
        'last_updated': None, 'masteryPercentage': 0
    }
    progress_id_for_logs = getattr(progress, 'id', 'Unknown')

    try:
        print(f"DEBUG: Serialize Progress: Starting serialization for progress ID: {progress_id_for_logs}")

        for attr in ['id', 'user_id', 'course_id', 'overall_progress', 'mastery_level']:
            if hasattr(progress, attr):
                serialized_data[attr] = getattr(progress, attr)

        if serialized_data['overall_progress'] is None: serialized_data['overall_progress'] = 0
        if serialized_data['mastery_level'] is None: serialized_data['mastery_level'] = 'beginner'

        if hasattr(progress, 'last_updated') and progress.last_updated:
            try:
                serialized_data['last_updated'] = progress.last_updated.isoformat()
            except Exception as e_date:
                print(f"DEBUG: Serialize Progress: Error serializing last_updated for progress ID {progress_id_for_logs}: {e_date}")

        json_fields_config = {
            'knowledge_areas': {}, 'weak_areas': [], 'strong_areas': [],
            'recommended_topics': [], 'learning_curve': []
        }
        for field, default_value in json_fields_config.items():
            raw_value = getattr(progress, field, None)
            if isinstance(raw_value, str) and raw_value.strip():
                try:
                    serialized_data[field] = json.loads(raw_value)
                except json.JSONDecodeError as e_json:
                    print(f"DEBUG: Serialize Progress: JSONDecodeError for field '{field}' in progress ID {progress_id_for_logs}. Value(start): '{raw_value[:100]}...'. Error: {e_json}")
                    serialized_data[field] = default_value
                except Exception as e_gen:
                    print(f"DEBUG: Serialize Progress: Generic error for field '{field}' in progress ID {progress_id_for_logs}. Value(start): '{raw_value[:100]}...'. Error: {e_gen}")
                    serialized_data[field] = default_value
            else:
                serialized_data[field] = default_value

        serialized_data['masteryPercentage'] = serialized_data['overall_progress']

        print(f"DEBUG: Serialize Progress: Successfully serialized progress ID: {progress_id_for_logs}")
        return serialized_data

    except Exception as e_main:
        print(f"CRITICAL_ERROR: Serialize Progress: Unexpected error during serialization of progress ID {progress_id_for_logs}: {e_main}")
        import traceback
        traceback.print_exc()
        return {
            'id': progress_id_for_logs, 'error': 'Critical serialization failure', 'details': str(e_main),
            'user_id': getattr(progress, 'user_id', None), 'course_id': getattr(progress, 'course_id', None),
            'knowledge_areas': {}, 'weak_areas': [], 'strong_areas': [], 'recommended_topics': [], 'learning_curve': [],
            'overall_progress': 0, 'mastery_level': 'beginner', 'last_updated': None, 'masteryPercentage': 0
        }

# Fallback skill extraction
def extract_skills_fallback(cv_text):
    patterns = [
        r'\b(?:Python|Java|JavaScript|C\+\+|C#|PHP|Ruby|Swift|Kotlin|Go|Rust)\b',
        r'\b(?:HTML|CSS|React|Angular|Vue|Node\.js|Express|Django|Flask)\b',
        r'\b(?:SQL|MySQL|PostgreSQL|MongoDB|SQLite|Oracle|Redis)\b',
        r'\b(?:Git|Docker|Kubernetes|AWS|Azure|GCP|Jenkins|CI/CD)\b',
        r'\b(?:Machine Learning|AI|Data Science|Analytics|TensorFlow|PyTorch)\b',
        r'\b(?:Project Management|Agile|Scrum|Leadership|Communication)\b',
    ]
    skills = []
    for pat in patterns:
        for m in re.finditer(pat, cv_text, re.IGNORECASE):
            s = m.group().strip()
            if s not in skills:
                skills.append(s)
    return {
        "current_skills": skills,
        "skill_categories": {"technical": skills},
        "experience_level": "unknown",
        "learning_recommendations": ["Consider learning complementary technologies"],
        "career_paths": ["Continue developing in your current domain"]
    }

# Gemini-based analysis
def analyze_skills_with_gemini(cv_text, job_description=None):
    if not GEMINI_API_KEY:
        return extract_skills_fallback(cv_text)
    
    if job_description and job_description.strip():
        prompt = f"""
Analyze this CV and job description to extract skills and provide guidance.

CV TEXT:
{cv_text[:3000]}

JOB DESCRIPTION:
{job_description[:2000]}

Provide JSON with current_skills, job_requirements, skill_gaps, matching_skills,
learning_recommendations, career_advice, skill_categories, experience_level.
"""
    else:
        prompt = f"""
Analyze this CV to extract skills and provide recommendations.

CV TEXT:
{cv_text[:4000]}

Provide JSON with current_skills, skill_categories, experience_level,
learning_recommendations, career_paths.
"""
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}], 
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 2000,
            "topP": 0.8
        }
    }
    
    try:
        res = requests.post(
            f"{GEMINI_API_URL}?key={GEMINI_API_KEY}", 
            json=payload, 
            headers={"Content-Type": "application/json"}, 
            timeout=30
        )
        res.raise_for_status()
        cand = res.json().get('candidates', [])
        if not cand:
            return extract_skills_fallback(cv_text)
        
        txt = cand[0]['content']['parts'][0]['text'].strip()
        jm = re.search(r'```json\s*(\{.*?\})\s*```', txt, re.DOTALL) or re.search(r'\{.*\}', txt, re.DOTALL)
        js = jm.group(1) if jm else txt
        data = json.loads(js)
        return data if isinstance(data, dict) and 'current_skills' in data else extract_skills_fallback(cv_text)
    except Exception:
        return extract_skills_fallback(cv_text)

# App factory
def create_app(config_name=None):
    # Check environment in development mode
    if DEVELOPMENT_MODE and check_environment:
        check_environment()
    
    app = Flask(__name__)

    # Templates - Fixed path resolution
    tpl_dirs = [FileSystemLoader(os.path.join(os.path.dirname(__file__), 'templates'))]
    animewatchlist_path = os.path.join(os.path.dirname(__file__), '..', 'animewatchlist')
    if os.path.isdir(animewatchlist_path): 
        tpl_dirs.append(FileSystemLoader(os.path.join(animewatchlist_path, 'templates')))
    app.jinja_loader = ChoiceLoader(tpl_dirs)

    # Config
    app.config.update({
        'SECRET_KEY': os.environ.get('SECRET_KEY', 'dev-secret'),
        'UPLOAD_FOLDER': os.path.join(os.path.dirname(__file__), 'uploads'),
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        'MAX_CONTENT_LENGTH': 10 * 1024 * 1024,
    })
    
    if DEVELOPMENT_MODE and not os.environ.get('DATABASE_URL'):
        app.config['SQLALCHEMY_DATABASE_URI'] = LOCAL_DATABASE_URL
    else:
        db_url = os.environ.get('DATABASE_URL')
        if db_url and db_url.startswith('postgres://'):
            db_url = db_url.replace('postgres://', 'postgresql://')
        app.config['SQLALCHEMY_DATABASE_URI'] = db_url or 'sqlite:///skillstown.db'

    # Ensure upload directory exists and is writable
    upload_dir = app.config['UPLOAD_FOLDER']
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir, exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    migrate = Migrate(app, db)

    @app.context_processor
    def inject(): 
        return {
            'current_year': datetime.now().year,
            'get_url_for': get_url_for
        }

    @app.template_filter('from_json')
    def from_json_filter(json_str):
        try:
            return json.loads(json_str) if json_str else {}
        except:
            return {}

    @app.template_filter('urlencode')
    def urlencode_filter(s):
        from urllib.parse import quote
        return quote(str(s)) if s else ''

    # Stats function
    def get_skillstown_stats(uid):
        try:
            total = UserCourse.query.filter_by(user_id=uid).count()
            enrolled = UserCourse.query.filter_by(user_id=uid, status='enrolled').count()
            in_p = UserCourse.query.filter_by(user_id=uid, status='in_progress').count()
            comp = UserCourse.query.filter_by(user_id=uid, status='completed').count()
            pct = (comp/total*100) if total else 0
            return {'total':total,'enrolled':enrolled,'in_progress':in_p,'completed':comp,'completion_percentage':pct}
        except:
            return {'total':0,'enrolled':0,'in_progress':0,'completed':0,'completion_percentage':0}

    # Initialize auth
    init_auth(app, get_url_for, get_skillstown_stats)

    with app.app_context(): 
        init_database()

    # Helper functions for quiz recommendations
    def generate_course_recommendations_from_quiz(attempt, api_attempts):
        """Generate course recommendations based on quiz performance"""
        score = attempt.score or 0
        catalog = load_course_catalog()
        
        recommendations = {
            'remedial_courses': [],
            'next_courses': [],
            'advanced_courses': [],
            'specific_advice': ''
        }
        
        # Determine recommendations based on score
        if score < 60:
            # Low score - recommend foundational courses
            recommendations['specific_advice'] = "Focus on strengthening your foundation in this subject area. The recommended courses will help you build core competencies."
            recommendations['remedial_courses'] = get_foundational_courses(catalog)
        elif score < 80:
            # Medium score - recommend intermediate courses
            recommendations['specific_advice'] = "You have a good foundation! Continue building your skills with these intermediate courses."
            recommendations['next_courses'] = get_intermediate_courses(catalog)
        else:
            # High score - recommend advanced courses
            recommendations['specific_advice'] = "Excellent work! You're ready for advanced topics that will set you apart."
            recommendations['advanced_courses'] = get_advanced_courses(catalog)
        
        return recommendations

    def generate_basic_recommendations_from_score(score):
        """Generate basic recommendations when API is unavailable"""
        catalog = load_course_catalog()
        
        recommendations = {
            'remedial_courses': [],
            'next_courses': [],
            'advanced_courses': [],
            'specific_advice': ''
        }
        
        if score < 60:
            recommendations['specific_advice'] = "Focus on foundational skills to improve your understanding."
            recommendations['remedial_courses'] = get_foundational_courses(catalog)
        elif score < 80:
            recommendations['specific_advice'] = "Great progress! Continue with intermediate level courses."
            recommendations['next_courses'] = get_intermediate_courses(catalog)
        else:
            recommendations['specific_advice'] = "Excellent! You're ready for advanced challenges."
            recommendations['advanced_courses'] = get_advanced_courses(catalog)
        
        return recommendations

    def get_foundational_courses(catalog):
        """Get beginner/foundational courses from catalog"""
        courses = []
        for category in catalog.get('categories', []):
            for course in category.get('courses', []):
                if course.get('level', '').lower() in ['beginner', 'basic', 'foundational']:
                    courses.append({
                        'name': course['name'],
                        'category': category['name'],
                        'reason': f"Strengthen foundation in {category['name'].lower()}"
                    })
                    if len(courses) >= 4:
                        break
            if len(courses) >= 4:
                break
        return courses

    def get_intermediate_courses(catalog):
        """Get intermediate courses from catalog"""
        courses = []
        for category in catalog.get('categories', []):
            for course in category.get('courses', []):
                if course.get('level', '').lower() in ['intermediate', 'medium']:
                    courses.append({
                        'name': course['name'],
                        'category': category['name'],
                        'reason': f"Build expertise in {category['name'].lower()}"
                    })
                    if len(courses) >= 4:
                        break
            if len(courses) >= 4:
                break
        return courses

    def get_advanced_courses(catalog):
        """Get advanced courses from catalog"""
        courses = []
        for category in catalog.get('categories', []):
            for course in category.get('courses', []):
                if course.get('level', '').lower() in ['advanced', 'expert', 'professional']:
                    courses.append({
                        'name': course['name'],
                        'category': category['name'],
                        'reason': f"Master advanced {category['name'].lower()} concepts"
                    })
                    if len(courses) >= 4:
                        break
            if len(courses) >= 4:
                break
        return courses

    def generate_course_recommendations_from_progress(progress, recent_attempts):
        """Generate course recommendations based on learning progress and recent attempts."""
        catalog = load_course_catalog()
        recommendations = {
            'remedial_courses': [],
            'next_courses': [],
            'advanced_courses': [],
            'specific_advice': ''
        }

        if not progress:
            recommendations['specific_advice'] = "We need more data to provide personalized recommendations. Please complete a quiz for this course."
            # Provide some generic starting courses if no progress
            recommendations['next_courses'] = get_intermediate_courses(catalog)[:2] # Suggest a couple of general courses
            return recommendations

        mastery_level = progress.mastery_level.lower() if progress.mastery_level else 'beginner'
        overall_progress_score = progress.overall_progress or 0
        
        # Try to parse weak_areas and strong_areas
        try:
            weak_areas = json.loads(progress.weak_areas) if progress.weak_areas else []
        except json.JSONDecodeError:
            weak_areas = []
        try:
            strong_areas = json.loads(progress.strong_areas) if progress.strong_areas else []
        except json.JSONDecodeError:
            strong_areas = []

        if mastery_level == 'beginner' or overall_progress_score < 50:
            recommendations['specific_advice'] = "You're at the beginner stage. Focus on building a strong foundation. "
            if weak_areas:
                recommendations['specific_advice'] += f"Consider revisiting topics related to: {', '.join(weak_areas)}. "
            recommendations['remedial_courses'] = get_foundational_courses(catalog)
            # Suggest next steps if some strong areas exist or score is not too low
            if overall_progress_score > 30 or strong_areas:
                 recommendations['next_courses'] = get_intermediate_courses(catalog)[:1] 

        elif mastery_level == 'intermediate' or overall_progress_score < 75:
            recommendations['specific_advice'] = "You're making good progress at the intermediate level! "
            if weak_areas:
                recommendations['specific_advice'] += f"To advance, focus on improving in: {', '.join(weak_areas)}. "
            if strong_areas:
                recommendations['specific_advice'] += f"Leverage your strengths in: {', '.join(strong_areas)}. "
            recommendations['next_courses'] = get_intermediate_courses(catalog)
            recommendations['advanced_courses'] = get_advanced_courses(catalog)[:1] # Suggest a taste of advanced

        elif mastery_level == 'advanced' or overall_progress_score < 90:
            recommendations['specific_advice'] = "You're at an advanced stage! Keep challenging yourself. "
            if weak_areas:
                recommendations['specific_advice'] += f"Refine your skills in: {', '.join(weak_areas)}. "
            recommendations['advanced_courses'] = get_advanced_courses(catalog)
            # Could also suggest related expert courses or specializations

        elif mastery_level == 'expert' or overall_progress_score >= 90:
            recommendations['specific_advice'] = "Excellent! You've reached an expert level in this area. "
            if strong_areas:
                 recommendations['specific_advice'] += f"You show mastery in: {', '.join(strong_areas)}. "
            recommendations['specific_advice'] += "Consider exploring specialized topics or mentoring others."
            # Suggest highly specialized or new/emerging related courses
            recommendations['advanced_courses'] = get_advanced_courses(catalog) # Offer more advanced options

        # Fallback if no specific category fits well
        if not recommendations['remedial_courses'] and not recommendations['next_courses'] and not recommendations['advanced_courses']:
            recommendations['next_courses'] = get_intermediate_courses(catalog)
            if not recommendations['specific_advice']:
                 recommendations['specific_advice'] = "Continue exploring courses to expand your knowledge."

        return recommendations

    def update_user_learning_progress(user_id, course_id, attempt_data, quiz_attempt):
        """Update user's learning progress based on quiz performance"""
        try:
            # Get or create learning progress
            progress = UserLearningProgress.query.filter_by(
                user_id=user_id,
                course_id=str(course_id)
            ).first()
            
            if not progress:
                progress = UserLearningProgress(
                    user_id=user_id,
                    course_id=str(course_id),
                    knowledge_areas='{}',
                    weak_areas='[]',
                    strong_areas='[]',
                    recommended_topics='[]',
                    learning_curve='[]',
                    overall_progress=0,
                    mastery_level='beginner'
                )
                db.session.add(progress)
            
            # Extract performance data from attempt
            score = quiz_attempt.score or 0
            
            # Update overall progress (weighted average)
            current_curve = json.loads(progress.learning_curve) if progress.learning_curve else []
            current_curve.append({
                'date': datetime.utcnow().isoformat(),
                'overallScore': score,
                'attemptId': quiz_attempt.id # Assuming quiz_attempt has an 'id' field for the local DB attempt ID
            })
            
            # Keep only last 20 attempts
            if len(current_curve) > 20:
                current_curve = current_curve[-20:]
            
            progress.learning_curve = json.dumps(current_curve)
            
            # Calculate new overall progress (average of recent attempts)
            if current_curve: # Ensure current_curve is not empty
                recent_scores = [entry['overallScore'] for entry in current_curve[-5:] if 'overallScore' in entry]
                if recent_scores: # Ensure recent_scores is not empty
                    progress.overall_progress = round(sum(recent_scores) / len(recent_scores))
                else:
                    progress.overall_progress = score # Fallback to current score if no recent scores
            else:
                progress.overall_progress = score # Fallback if learning curve was initially empty

            # Update mastery level based on progress
            if progress.overall_progress >= 90:
                progress.mastery_level = 'expert'
            elif progress.overall_progress >= 75:
                progress.mastery_level = 'advanced'
            elif progress.overall_progress >= 50:
                progress.mastery_level = 'intermediate'
            else:
                progress.mastery_level = 'beginner'
            
            progress.last_updated = datetime.utcnow()
            
            # The calling function (complete_quiz_attempt) will handle db.session.commit()
            print(f"[DEBUG] Updated learning progress for user {user_id}, course {course_id}. New overall progress: {progress.overall_progress}, Mastery: {progress.mastery_level}")
            return progress # Return the progress object
            
        except Exception as e:
            print(f"Error updating learning progress: {e}")
            traceback.print_exc() # Print full traceback for debugging
            # db.session.rollback() # Consider rolling back if this function is part of a larger transaction and fails
            return None

    # Helpers
    COURSE_CATALOG_PATH = os.path.join(os.path.dirname(__file__), 'static', 'data', 'course_catalog.json')
    
    def load_course_catalog():
        try:
            with open(COURSE_CATALOG_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {'categories': []}
    
    def calc_score(q, t, d): 
        return sum(3 for w in q.split() if w in t.lower()) + sum(1 for w in q.split() if w in d.lower())
    
    def search_courses(query, catalog=None):
        if not catalog: 
            catalog = load_course_catalog()
        q = query.lower().strip()
        res = []
        for cat in catalog.get('categories', []):
            for c in cat.get('courses', []):
                sc = calc_score(q, c['name'], c.get('description', ''))
                if sc > 0: 
                    res.append({
                        'category': cat['name'],
                        'course': c['name'],
                        'description': c.get('description', ''),
                        'relevance_score': sc
                    })
        return sorted(res, key=lambda x: x['relevance_score'], reverse=True)
    
    def allowed_file(fn): 
        return '.' in fn and fn.rsplit('.', 1)[1].lower() == 'pdf'
    
    def extract_text_from_pdf(fp):
        txt = ''
        try:
            with open(fp, 'rb') as f:
                r = PyPDF2.PdfReader(f)
                for p in r.pages:
                    try: 
                        txt += p.extract_text() or ''
                    except: 
                        continue
        except Exception as e:
            print(f"Error reading PDF: {e}")
        return txt.strip()

    # Initialize self-pinging service in production
    if is_production():
        global ping_service
        app_url = os.environ.get('RENDER_EXTERNAL_URL', 'https://skillstown-final.onrender.com')
        quiz_api_url = QUIZ_API_BASE_URL
        narretex_url = NARRETEX_API_URL
        qdrant_url = os.environ.get('QDRANT_HOST', 'https://qdrant-vector-db-t8ao.onrender.com')
        
        ping_service = SelfPingService(app_url, quiz_api_url, narretex_url, qdrant_url)
        
        # Start pinging after a delay to ensure app is fully started
        def delayed_start():
            time.sleep(30)  # Wait 30 seconds before starting
            ping_service.start_pinging()
        
        threading.Thread(target=delayed_start, daemon=True).start()

    # Routes
    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            email = request.form.get('email')
            password = request.form.get('password')
            
            user = Student.query.filter_by(email=email).first()
            if user and check_password_hash(user.password_hash, password):
                login_user(user)
                return redirect(get_url_for('index'))
            else:
                flash('Invalid email or password', 'error')
        
        return render_template('auth/login.html')

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if request.method == 'POST':
            name = request.form.get('name')
            email = request.form.get('email')
            password = request.form.get('password')
            
            if Student.query.filter_by(email=email).first():
                flash('Email already exists', 'error')
                return render_template('auth/register.html')
            
            user = Student(
                name=name,
                email=email,
                username=email,
                password_hash=generate_password_hash(password)
            )
            db.session.add(user)
            db.session.commit()
            
            login_user(user)
            flash('Registration successful!', 'success')
            return redirect(get_url_for('index'))
        
        return render_template('auth/register.html')

    @app.route('/logout')
    def logout():
        logout_user()
        return redirect(get_url_for('index'))

    # QUIZ ROUTES - NEW INTEGRATION
    @app.route('/course/<int:course_id>/generate-quiz', methods=['POST'])
    @login_required
    def generate_quiz(course_id):
        """Generate a new quiz for a course"""
        try:
            # Get the course from UserCourse table
            course = UserCourse.query.filter_by(id=course_id, user_id=current_user.id).first()
            if not course:
                return jsonify({
                    'success': False,
                    'error': 'Course not found or you do not have access to it'
                }), 404
            
            # Get or create quiz UUID for the user
            quiz_user_uuid = current_user.get_quiz_uuid()
            
            # Get course details to send to quiz API
            course_details = CourseDetail.query.filter_by(user_course_id=course_id).first()
            description = course_details.description if course_details else f"Learn {course.course_name} with practical examples and real-world applications."
            
            # Get course info from catalog for more details
            catalog_info = get_detailed_course_info(course.course_name)

            # NEW: Get user's learning progress for personalization
            learning_progress = UserLearningProgress.query.filter_by(
                user_id=current_user.id,
                course_id=str(course_id)  # Ensure course_id is string for comparison if stored as string
            ).first()
            
            # NEW: Get previous quiz attempts for iteration logic
            previous_attempts = CourseQuizAttempt.query.filter_by(
                user_id=current_user.id
            ).join(CourseQuiz).filter(
                CourseQuiz.user_course_id == course_id
            ).order_by(CourseQuizAttempt.completed_at.desc()).limit(5).all()
            
            # Prepare the request payload for quiz API
            quiz_payload = {
                "user_id": quiz_user_uuid,
                "course": {
                    "id": course_id, # ADDED this
                    "name": course.course_name,
                    "description": description,
                    "duration": catalog_info.get('duration', 'Variable'), # Updated default
                    "level": catalog_info.get('level', 'Intermediate'),
                    "skills": catalog_info.get('skills', []),
                    "projects": catalog_info.get('projects', []),
                    "career_paths": catalog_info.get('career_paths', [])
                },
                # NEW: Add personalization data
                "personalization": {
                    "has_progress": learning_progress is not None,
                    "mastery_level": learning_progress.mastery_level if learning_progress else "beginner",
                    "weak_areas": json.loads(learning_progress.weak_areas) if learning_progress and learning_progress.weak_areas else [],
                    "strong_areas": json.loads(learning_progress.strong_areas) if learning_progress and learning_progress.strong_areas else [],
                    "previous_attempts": len(previous_attempts),
                    "iteration_number": len(previous_attempts) + 1
                }
            }
            
            print(f"[DEBUG] Sending quiz payload: {json.dumps(quiz_payload, indent=2)}") # Enhanced debug
            
            # Add retry logic for Render's cold start issues
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    # Call the quiz API to create quiz
                    response = requests.post(
                        f"{QUIZ_API_BASE_URL}/quiz/create-ai-from-course",
                        json=quiz_payload,
                        headers=get_quiz_api_headers(),
                        timeout=90  # Increased timeout for Render
                    )
                    
                    print(f"[DEBUG] Quiz API response: {response.status_code} - {response.text}")
                    
                    if response.status_code == 201:  # Note: API returns 201, not 200
                        quiz_data = response.json()
                        
                        # Save quiz info to our database
                        course_quiz = CourseQuiz(
                            user_course_id=course_id,
                            quiz_api_id=quiz_data['quizId'],
                            quiz_title=quiz_data['title'],
                            quiz_description=quiz_data['description'],
                            questions_count=quiz_data['questionsCount']
                        )
                        db.session.add(course_quiz)
                        db.session.commit()
                        
                        return jsonify({
                            'success': True,
                            'quiz_id': quiz_data['quizId'],
                            'title': quiz_data['title'],
                            'description': quiz_data['description'],
                            'questions_count': quiz_data['questionsCount'],
                            'message': 'Quiz generated successfully!'
                        })
                    elif response.status_code == 503:
                        # Service temporarily unavailable, likely cold start
                        print(f"⏳ Quiz API cold start detected, attempt {attempt + 1}/{max_retries}")
                        if attempt < max_retries - 1:
                            time.sleep(10 * (attempt + 1))  # Exponential backoff
                            continue
                    else:
                        print(f"Quiz API error: {response.status_code} - {response.text}")
                        break
                        
                except requests.exceptions.Timeout:
                    print(f"⏰ Quiz API timeout on attempt {attempt + 1}/{max_retries}")
                    if attempt < max_retries - 1:
                        time.sleep(5 * (attempt + 1))
                        continue
                except requests.exceptions.ConnectionError:
                    print(f"🔌 Quiz API connection error on attempt {attempt + 1}/{max_retries}")
                    if attempt < max_retries - 1:
                        time.sleep(5 * (attempt + 1))
                        continue
            
            return jsonify({
                'success': False,
                'error': f'Quiz service temporarily unavailable. Please try again in a few moments.'
            }), 503
                    
        except Exception as e:
            print(f"Error generating quiz: {e}")
            traceback.print_exc()
            return jsonify({
                'success': False,
                'error': f'Internal error: {str(e)}'
            }), 500

    def check_service_health(url, timeout=5):
        try:
            response = requests.get(f"{url}/health", timeout=timeout)
            return response.status_code == 200
        except:
            return False

    @app.route('/quiz/<quiz_id>/details')
    @login_required
    def get_quiz_details(quiz_id):
        """Get quiz details for taking the quiz"""
        try:
            if not check_service_health(QUIZ_API_BASE_URL):
                return jsonify({'error': 'Quiz service temporarily unavailable'}), 503
            
            print(f"[DEBUG] Getting quiz details for quiz_id: {quiz_id}")
            
            # Verify user owns this quiz
            course_quiz = CourseQuiz.query.filter_by(quiz_api_id=quiz_id).first()
            if not course_quiz:
                print(f"[DEBUG] Quiz not found in database: {quiz_id}")
                return jsonify({'error': 'Quiz not found'}), 404
                    
            user_course = UserCourse.query.filter_by(
                id=course_quiz.user_course_id, 
                user_id=current_user.id
            ).first()
            if not user_course:
                print(f"[DEBUG] Access denied for user {current_user.id} to quiz {quiz_id}")
                return jsonify({'error': 'Access denied'}), 403
            
            # Get the user's quiz UUID
            quiz_user_uuid = current_user.get_quiz_uuid()
            
            # Only use the "from-course" endpoint with Authorization header
            endpoints_to_try = [f"/quiz/{quiz_id}/from-course"]  # Use GET /quiz/:quizId/from-course
            
            response = None
            for endpoint in endpoints_to_try:
                try:
                    print(f"[DEBUG] Trying endpoint: {QUIZ_API_BASE_URL}{endpoint}")
                    response = requests.get(
                        f"{QUIZ_API_BASE_URL}{endpoint}",
                        headers=get_quiz_api_headers(),
                        timeout=30
                    )
                    print(f"[DEBUG] Response status: {response.status_code}")
                    
                    if response.status_code == 200:
                        print(f"[DEBUG] Success with endpoint: {endpoint}")
                        break
                    else:
                        print(f"[DEBUG] Failed with endpoint {endpoint}: {response.status_code} - {response.text}")
                        
                except Exception as e:
                    print(f"[DEBUG] Exception with endpoint {endpoint}: {e}")
                    continue
            
            if response and response.status_code == 200:
                quiz_data = response.json()
                print(f"[DEBUG] Quiz data received: {list(quiz_data.keys()) if isinstance(quiz_data, dict) else type(quiz_data)}")
                return jsonify(quiz_data)
            else:
                error_msg = f'Quiz API error: {response.status_code if response else "No response"}' 
                if response:
                    error_msg += f" - {response.text}"
                print(f"[DEBUG] Final error: {error_msg}")
                return jsonify({'error': error_msg}), 500
                        
        except Exception as e:
            print(f"[DEBUG] Exception in get_quiz_details: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500

    @app.route('/quiz/<quiz_id>/start', methods=['POST'])
    @login_required  
    def start_quiz_attempt(quiz_id):
        """Start a new quiz attempt"""
        try:
            print(f"[DEBUG] Starting quiz attempt for quiz_id: {quiz_id}")
            
            # Verify user owns this quiz
            course_quiz = CourseQuiz.query.filter_by(quiz_api_id=quiz_id).first()
            if not course_quiz:
                print(f"[DEBUG] Quiz not found: {quiz_id}")
                return jsonify({'error': 'Quiz not found'}), 404
                    
            user_course = UserCourse.query.filter_by(
                id=course_quiz.user_course_id,
                user_id=current_user.id
            ).first()
            if not user_course:
                print(f"[DEBUG] Access denied for quiz: {quiz_id}")
                return jsonify({'error': 'Access denied'}), 403
            
            # Get the user's quiz UUID
            quiz_user_uuid = current_user.get_quiz_uuid()
            
            # Store the original course_id for traceability - this is important for learning progress
            original_course_id = user_course.id
            
            # Only the "attempt-from-course" endpoint uses header auth
            endpoints_to_try = [f"/quiz/{quiz_id}/{quiz_user_uuid}/attempt-from-course"]  # Use POST /quiz/:quizId/:userId/attempt-from-course
            
            response = None
            for endpoint in endpoints_to_try:
                try:
                    print(f"[DEBUG] Trying start endpoint: {QUIZ_API_BASE_URL}{endpoint}")
                    response = requests.post(
                        f"{QUIZ_API_BASE_URL}{endpoint}",
                        json={'user_id': quiz_user_uuid},
                        headers=get_quiz_api_headers(),
                        timeout=30
                    )
                    print(f"[DEBUG] Start response status: {response.status_code}")
                     
                    if response.status_code in [200, 201]:
                        print(f"[DEBUG] Success starting with endpoint: {endpoint}")
                        break
                    else:
                        print(f"[DEBUG] Failed starting with endpoint {endpoint}: {response.status_code} - {response.text}")
                     
                except Exception as e:
                    print(f"[DEBUG] Exception starting with endpoint {endpoint}: {e}")
                    continue
            
            if response and response.status_code in [200, 201]:
                attempt_data = response.json()
                print(f"[DEBUG] Attempt data: {attempt_data}")
                
                # Save attempt to our database with the original course_id for better tracking
                quiz_attempt = CourseQuizAttempt(
                    user_id=current_user.id,
                    course_quiz_id=course_quiz.id,
                    course_id=user_course.id,
                    attempt_api_id=attempt_data.get('attemptId', attempt_data.get('id', 'unknown'))
                )
                db.session.add(quiz_attempt)
                db.session.commit()
                
                return jsonify(attempt_data)
            else:
                error_msg = f'Quiz API error: {response.status_code if response else "No response"}'
                if response:
                    error_msg += f" - {response.text}"
                print(f"[DEBUG] Start attempt error: {error_msg}")
                return jsonify({'error': error_msg}), 500
                        
        except Exception as e:
            print(f"[DEBUG] Exception in start_quiz_attempt: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500

    @app.route('/quiz/attempt/<attempt_id>/complete', methods=['POST'])
    @login_required
    def complete_quiz_attempt(attempt_id):
        """Complete a quiz attempt with user answers"""
        try:
            print(f"[DEBUG] Completing quiz attempt: {attempt_id}")
            
            # Get the attempt from our database
            quiz_attempt_model = CourseQuizAttempt.query.filter_by( # Renamed to avoid conflict
                attempt_api_id=attempt_id,
                user_id=current_user.id
            ).first()
            if not quiz_attempt_model:
                print(f"[DEBUG] Quiz attempt not found: {attempt_id}")
                return jsonify({'error': 'Quiz attempt not found'}), 404
            
            # Get raw input and build payload with answers array
            raw_input = request.json
            # Ensure answers is an array under 'answers' key
            answers_list = raw_input if isinstance(raw_input, list) else raw_input.get('answers', [])
            payload = {'answers': answers_list}
            print(f"[DEBUG] Payload for complete-from-course: {payload}")
            
            # Get the user's quiz UUID
            quiz_user_uuid = current_user.get_quiz_uuid()
            # Only the "complete-from-course" endpoint uses header auth
            endpoints_to_try = [f"/quiz/attempt/{attempt_id}/{quiz_user_uuid}/complete-from-course"]  # Use POST /quiz/attempt/:attemptId/:userId/complete-from-course
            
            response = None
            for endpoint in endpoints_to_try:
                try:
                    print(f"[DEBUG] Trying complete endpoint: {QUIZ_API_BASE_URL}{endpoint}")
                    response = requests.post(
                        f"{QUIZ_API_BASE_URL}{endpoint}",
                        json=payload,
                        headers=get_quiz_api_headers(),
                        timeout=30
                    )
                    print(f"[DEBUG] Complete response status: {response.status_code}")
                    
                    if response.status_code == 200:
                        print(f"[DEBUG] Success completing with endpoint: {endpoint}")
                        break
                    else:
                        print(f"[DEBUG] Failed completing with endpoint {endpoint}: {response.status_code} - {response.text}")
                        
                except Exception as e:
                    print(f"[DEBUG] Exception completing with endpoint {endpoint}: {e}")
                    continue
            
            if response and response.status_code == 200:
                # Parse initial acknowledgment
                initial_data = response.json()
                print(f"[DEBUG] Initial complete response: {initial_data}")
                result_data = initial_data # Default to initial data
                # Attempt to fetch full result details
                try:
                    details_resp = requests.get(
                        f"{QUIZ_API_BASE_URL}/quiz/attempt/{attempt_id}/{quiz_user_uuid}/results-from-course",
                        headers=get_quiz_api_headers(),
                        timeout=30
                    )
                    if details_resp.status_code == 200:
                        result_data = details_resp.json() # Use detailed data if successful
                        print(f"[DEBUG] Fetched detailed result data: {result_data}")
                    else:
                        # result_data remains initial_data
                        print(f"[DEBUG] Detailed fetch failed, status {details_resp.status_code}, using initial response for results.")
                except Exception as e:
                    # result_data remains initial_data
                    print(f"[DEBUG] Exception fetching detailed results: {e}, using initial response for results.")

                # Update our attempt record with results if provided
                if 'results' in result_data:
                    r = result_data['results']
                    quiz_attempt_model.score = r.get('score', 0)
                    quiz_attempt_model.total_questions = r.get('totalQuestions', 0)
                    quiz_attempt_model.correct_answers = r.get('correct', 0)
                    quiz_attempt_model.feedback_strengths = json.dumps(r.get('strengths', '')) # Store as JSON
                    quiz_attempt_model.feedback_improvements = json.dumps(r.get('improvements', '')) # Store as JSON
                    quiz_attempt_model.user_answers = json.dumps(answers_list)
                    quiz_attempt_model.completed_at = datetime.utcnow()
                    # db.session.commit() # Commit will be done after learning progress update
                    print(f"[DEBUG] Quiz attempt model updated in memory with full results")

                if quiz_attempt_model.course_quiz and quiz_attempt_model.course_quiz.user_course_id:
                    original_course_id = quiz_attempt_model.course_quiz.user_course_id
                    update_user_learning_progress(
                        user_id=current_user.id,
                        course_id=original_course_id,
                        attempt_data=result_data, 
                        quiz_attempt=quiz_attempt_model
                    )
                else:
                    print(f"[ERROR] Could not determine original course_id for learning progress update. quiz_attempt_id: {quiz_attempt_model.id}")

                db.session.commit() # Commit both quiz_attempt_model and learning_progress changes
                print(f"[DEBUG] Database commit successful after quiz completion and learning progress update.")

                # Always return wrapped under 'results' for client display
                if 'results' in result_data:
                    return jsonify(result_data)
                else:
                    return jsonify({ 'results': result_data })
            else:
                error_msg = f'Quiz API error: {response.status_code if response else "No response"}'
                if response:
                    error_msg += f" - {response.text}"
                print(f"[DEBUG] Complete attempt error: {error_msg}")
                return jsonify({'error': error_msg}), 500
                        
        except Exception as e:
            db.session.rollback() # Rollback on any exception during the process
            print(f"[DEBUG] Exception in complete_quiz_attempt: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500

    # Add this after creating the app
    @app.route('/static/<path:filename>')
    def static_files(filename):
        return send_from_directory('static', filename)

    # Add this test route to check your quiz API connectivity
    @app.route('/test-quiz-api')
    @login_required
    def test_quiz_api():
        """Test route to check quiz API connectivity"""
        try:
            # Test basic connectivity
            response = requests.get(f"{QUIZ_API_BASE_URL}/health", timeout=10)
            
            api_status = {
                'quiz_api_base_url': QUIZ_API_BASE_URL,
                'health_check_status': response.status_code if response else 'No response',
                'health_check_response': response.text if response else 'No response'
            }
            
            return jsonify(api_status)
            
        except Exception as e:
            return jsonify({
                'error': str(e),
                'quiz_api_base_url': QUIZ_API_BASE_URL
            }), 500

    @app.route('/test-quiz-auth')
    @login_required
    def test_quiz_auth():
        """Test route to verify quiz API authentication with different methods"""
        try:
            access_token = os.environ.get('QUIZ_API_ACCESS_TOKEN', QUIZ_API_ACCESS_TOKEN)
            
            # Try different authentication methods
            auth_methods = [
                {'name': 'Bearer Token', 'headers': {'Content-Type': 'application/json', 'Authorization': f'Bearer {access_token}'}},
                {'name': 'Token Header', 'headers': {'Content-Type': 'application/json', 'Authorization': f'Token {access_token}'}},
                {'name': 'X-API-Key', 'headers': {'Content-Type': 'application/json', 'X-API-Key': access_token}},
                {'name': 'X-Access-Token', 'headers': {'Content-Type': 'application/json', 'X-Access-Token': access_token}},
                {'name': 'No Auth', 'headers': {'Content-Type': 'application/json'}},
            ]
            
            # Test endpoints
            test_endpoints = ['/health', '/status', '/']
            
            results = {}
            
            for method in auth_methods:
                results[method['name']] = {}
                for endpoint in test_endpoints:
                    try:
                        response = requests.get(
                            f"{QUIZ_API_BASE_URL}{endpoint}",
                            headers=method['headers'],
                            timeout=10
                        )
                        results[method['name']][endpoint] = {
                            'status': response.status_code,
                            'response': response.text[:200] if response.text else 'No response body'
                        }
                    except Exception as e:
                        results[method['name']][endpoint] = {
                            'error': str(e)
                        }
            
            return jsonify({
                'quiz_api_base_url': QUIZ_API_BASE_URL,
                'token_preview': f"{access_token[:20]}..." if access_token else "NO TOKEN",
                'authentication_test_results': results
            })
            
        except Exception as e:
            return jsonify({
                'error': str(e),
                'quiz_api_base_url': QUIZ_API_BASE_URL
            }), 500

    @app.route('/course/<int:course_id>/quiz-attempts')
    @login_required
    def get_course_quiz_attempts(course_id):
        """Get all quiz attempts for a course"""
        try:
            # Verify user owns this course
            course = UserCourse.query.filter_by(id=course_id, user_id=current_user.id).first()
            if not course:
                return jsonify({'error': 'Course not found'}), 404
            
            # Get all quiz attempts for this course
            quiz_attempts = db.session.query(CourseQuizAttempt).join(
                CourseQuiz, CourseQuizAttempt.course_quiz_id == CourseQuiz.id
            ).filter(
                CourseQuiz.user_course_id == course_id,
                CourseQuizAttempt.user_id == current_user.id
            ).order_by(CourseQuizAttempt.completed_at.desc()).all()
            
            attempts_data = []
            for attempt in quiz_attempts:
                attempts_data.append({
                    'id': attempt.id,
                    'attempt_api_id': attempt.attempt_api_id,
                    'score': attempt.score,
                    'total_questions': attempt.total_questions,
                    'correct_answers': attempt.correct_answers,
                    'feedback_strengths': attempt.feedback_strengths,
                    'feedback_improvements': attempt.feedback_improvements,
                    'completed_at': attempt.completed_at.isoformat() if attempt.completed_at else None,
                    'quiz_title': attempt.course_quiz.quiz_title
                })
            
            return jsonify({'attempts': attempts_data})
            
        except Exception as e:
            print(f"Error getting quiz attempts: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/course/<int:course_id>/quiz-recommendations')
    @login_required
    def get_quiz_recommendations(course_id):
        """Get AI-generated course recommendations based on quiz performance and learning progress"""
        try:
            # Get learning progress
            progress = UserLearningProgress.query.filter_by(
                user_id=current_user.id,
                course_id=str(course_id)
            ).first()
            
            # Get recent attempts
            recent_attempts = CourseQuizAttempt.query.filter_by(
                user_id=current_user.id
            ).join(CourseQuiz).filter(
                CourseQuiz.user_course_id == course_id,
                CourseQuizAttempt.score.isnot(None) # Ensure attempts have scores
            ).order_by(CourseQuizAttempt.completed_at.desc()).limit(5).all()
            
            # Generate enhanced recommendations
            recommendations = generate_course_recommendations_from_progress(progress, recent_attempts)
            
            # Serialize progress data safely
            progress_data = serialize_learning_progress(progress)
            
            return jsonify({
                'recommendations': recommendations,
                'progress': progress_data
            })
        except Exception as e:
            print(f"Error getting quiz recommendations: {e}")
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500

    # PODCAST ROUTES
    @app.route('/course/<int:course_id>/generate-podcast', methods=['POST'])
    @login_required
    def generate_course_podcast(course_id):
        course = UserCourse.query.filter_by(id=course_id, user_id=current_user.id).first_or_404()
        
        try:
            print(f"=== PODCAST GENERATION DEBUG ===")
            print(f"Course: {course.course_name}")
            print(f"Course ID: {course_id}")
            
            # Get course details for more context
            course_details = CourseDetail.query.filter_by(user_course_id=course_id).first()
            description = course_details.description if course_details else f"Learn {course.course_name} with practical examples and real-world applications."
            
            print(f"Description length: {len(description)} chars")
            print(f"Description preview: {description[:100]}...")
            
            # Generate podcast
            print("Calling generate_podcast_for_course...")
            audio_data = generate_podcast_for_course(course.course_name, description)
            
            print(f"Received audio_data: {type(audio_data)}")
            if audio_data:
                print(f"Audio data size: {len(audio_data)} bytes")
                print(f"Audio data preview: {audio_data[:20] if len(audio_data) >= 20 else audio_data}")
                
                # Check if it looks like WAV data
                if audio_data.startswith(b'RIFF') and b'WAVE' in audio_data[:12]:
                    print("✅ Audio data appears to be valid WAV format")
                else:
                    print("❌ WARNING: Audio data does not appear to be WAV format")
                    print(f"First 20 bytes: {audio_data[:20]}")
            else:
                print("❌ ERROR: audio_data is None or empty")
            
            if audio_data and len(audio_data) > 0:
                # Store the audio data in session or database for streaming
                # For now, we'll return it directly for streaming (no attachment header)
                print("Returning successful audio response for streaming")
                return Response(
                    audio_data,
                    mimetype='audio/wav',
                    headers={
                        'Content-Length': str(len(audio_data)),
                        'Accept-Ranges': 'bytes',
                        'Cache-Control': 'no-cache'
                    }
                )
            else:
                print("❌ ERROR: Empty or invalid audio data")
                flash('Podcast service is temporarily unavailable. Please try again later.', 'warning')
                return redirect(get_url_for('course_detail', course_id=course_id))
        except Exception as e:
            print(f"❌ EXCEPTION in podcast generation: {e}")
            traceback.print_exc()
            flash('Podcast service is temporarily unavailable. Please try again later.', 'warning')
            return redirect(get_url_for('course_detail', course_id=course_id))

    @app.route('/test-podcast')
    @login_required
    def test_podcast():
        """Test route for podcast generation"""
        try:
            test_audio = generate_podcast_for_course(
                "Python Programming", 
                "Learn Python from basics to advanced concepts including data structures, algorithms, and web development."
            )
            
            if test_audio:
                return Response(
                    test_audio,
                    mimetype='audio/wav',
                    headers={'Content-Disposition': 'attachment; filename="test_podcast.wav"'}
                )
            else:
                return "Podcast generation failed", 500
                
        except Exception as e:
            return f"Error: {e}", 500

    # CV ANALYSIS ROUTES
    @app.route('/assessment')
    @login_required
    def assessment():
        return render_template('assessment/assessment.html')

    @app.route('/assessment', methods=['POST'])
    @login_required
    def upload_cv():
        if 'cv_file' not in request.files:
            flash('Please select a file', 'error')
            return redirect(get_url_for('assessment'))
        
        file = request.files['cv_file']
        job_description = request.form.get('job_description', '').strip()
        
        if file.filename == '':
            flash('Please select a file', 'error')
            return redirect(get_url_for('assessment'))
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            os.makedirs(current_app.config['UPLOAD_FOLDER'], exist_ok=True)
            filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            try:
                cv_text = extract_text_from_pdf(filepath)
                os.remove(filepath)  # Clean up uploaded file
                
                if not cv_text.strip():
                    flash('Could not extract text from PDF. Please ensure it\'s not an image-only PDF.', 'error')
                    return redirect(get_url_for('assessment'))
                
                # Analyze with Gemini
                analysis = analyze_skills_with_gemini(cv_text, job_description)
                skills = analysis.get('current_skills', [])
                
                # Save to database
                profile = UserProfile(
                    user_id=current_user.id,
                    cv_text=cv_text,
                    job_description=job_description if job_description else None,
                    skills=json.dumps(skills),
                    skill_analysis=json.dumps(analysis)
                )
                db.session.add(profile)
                db.session.commit()
                
                return redirect(get_url_for('results', profile_id=profile.id))
                
            except Exception as e:
                print(f"Error processing CV: {e}")
        flash('Invalid file format. Please upload a PDF file.', 'error')
        return redirect(get_url_for('assessment'))

    @app.route('/results/<int:profile_id>')
    @login_required
    def results(profile_id):
        profile = UserProfile.query.filter_by(id=profile_id, user_id=current_user.id).first_or_404()
        
        try:
            skills = json.loads(profile.skills) if profile.skills else []
            full_analysis = json.loads(profile.skill_analysis) if profile.skill_analysis else {}
        except:
            skills = []
            full_analysis = {}
        
        # Determine skill categories for recommendations
        has_programming_skills = any(skill.lower() in ['python', 'java', 'javascript', 'c++', 'c#'] for skill in skills)
        has_data_skills = any(skill.lower() in ['data science', 'machine learning', 'analytics', 'sql'] for skill in skills)
        has_web_skills = any(skill.lower() in ['html', 'css', 'react', 'angular', 'web development'] for skill in skills)
        has_devops_skills = any(skill.lower() in ['docker', 'kubernetes', 'aws', 'azure', 'devops'] for skill in skills)
        
        return render_template('assessment/results.html', 
                             profile=profile, 
                             skills=skills, 
                             full_analysis=full_analysis,
                             has_programming_skills=has_programming_skills,
                             has_data_skills=has_data_skills,
                             has_web_skills=has_web_skills,
                             has_devops_skills=has_devops_skills)

    # COURSE MANAGEMENT ROUTES
    @app.route('/search')
    def search():
        query = request.args.get('query', '')
        results = []
        if query:
            results = search_courses(query)
        return render_template('courses/search.html', query=query, results=results)

    @app.route('/enroll', methods=['POST'])
    @login_required
    def enroll_course():
        category = request.form.get('category')
        course = request.form.get('course')
        
        existing = UserCourse.query.filter_by(
            user_id=current_user.id, 
            course_name=course
        ).first()
        
        if existing:
            return jsonify({'success': False, 'message': 'Already enrolled in this course'})
        
        user_course = UserCourse(
            user_id=current_user.id,
            category=category,
            course_name=course,
            status='enrolled'
        )
        db.session.add(user_course)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Successfully enrolled!'})

    @app.route('/my-courses')
    @login_required
    def my_courses():
        courses = UserCourse.query.filter_by(user_id=current_user.id).order_by(UserCourse.created_at.desc()).all()
        stats = get_skillstown_stats(current_user.id)
        return render_template('courses/my_courses.html', courses=courses, stats=stats)

    @app.route('/course/<int:course_id>')
    @login_required
    def course_detail(course_id):
        course = UserCourse.query.filter_by(id=course_id, user_id=current_user.id).first_or_404()
        
        # Get or create course details
        course_details = CourseDetail.query.filter_by(user_course_id=course_id).first()
        if not course_details:
            # Create sample course details
            sample_materials = {
                "materials": [
                    {
                        "title": f"Introduction to {course.course_name}",
                        "type": "lesson",
                        "duration": "2 hours",
                        "topics": ["Fundamentals", "Getting Started", "Overview"],
                        "description": f"Learn the basics of {course.course_name} and get started with practical examples."
                    },
                    {
                        "title": f"Intermediate {course.course_name}",
                        "type": "lesson", 
                        "duration": "3 hours",
                        "topics": ["Advanced Concepts", "Best Practices", "Real-world Applications"],
                        "description": f"Dive deeper into {course.course_name} with advanced techniques and industry practices."
                    },
                    {
                        "title": f"{course.course_name} Project",
                        "type": "project",
                        "duration": "5 hours", 
                        "topics": ["Hands-on Practice", "Portfolio Building", "Implementation"],
                        "description": f"Build a complete project using {course.course_name} to demonstrate your skills."
                    }
                ]
            }
            
            course_details = CourseDetail(
                user_course_id=course_id,
                description=f"Learn {course.course_name} with hands-on projects and real-world applications. This comprehensive course covers everything from basics to advanced concepts.",
                progress_percentage=0,
                materials=json.dumps(sample_materials)
            )
            db.session.add(course_details)
            db.session.commit()
        
        # Parse materials
        try:
            materials = json.loads(course_details.materials) if course_details.materials else {"materials": []}
        except:
            materials = {"materials": []}
        
        return render_template('courses/course_detail.html', 
                             course=course, 
                             course_details=course_details,
                             materials=materials,
                             quiz_proxy_url=os.environ.get('QUIZ_PROXY_URL', 'http://localhost:8081'),
                            quiz_api_access_token=os.environ.get('QUIZ_API_ACCESS_TOKEN', QUIZ_API_ACCESS_TOKEN)
                            )

    @app.route('/course/<int:course_id>/update-status', methods=['POST'])
    @login_required
    def update_course_status(course_id):
        course = UserCourse.query.filter_by(id=course_id, user_id=current_user.id).first_or_404()
        new_status = request.form.get('status')
        
        if new_status in ['enrolled', 'in_progress', 'completed']:
            course.status = new_status
            if new_status == 'completed':
                # Update course details progress
                course_details = CourseDetail.query.filter_by(user_course_id=course_id).first()
                if course_details:
                    course_details.progress_percentage = 100
                    course_details.completed_at = datetime.utcnow()
            
            db.session.commit()
            flash(f'Course status updated to {new_status}!', 'success')
        
        return redirect(get_url_for('course_detail', course_id=course_id))

    @app.route('/profile')
    @login_required
    def skillstown_user_profile():
        stats = get_skillstown_stats(current_user.id)
        recent_courses = UserCourse.query.filter_by(user_id=current_user.id).order_by(UserCourse.created_at.desc()).limit(5).all()
        return render_template('profile.html', stats=stats, recent_courses=recent_courses)

    @app.route('/about')
    def about():
        return render_template('about.html')

    # Admin routes
    @app.route('/admin/reset-skillstown-tables', methods=['POST'])
    @login_required
    def reset_skillstown_tables():
        if current_user.email != 'bentakaki7@gmail.com':
            flash('Not authorized', 'danger')
            return redirect(get_url_for('skillstown_user_profile'))
        
        try:
            cmds = [
                "DROP TABLE IF EXISTS skillstown_user_courses CASCADE;",
                "DROP TABLE IF EXISTS skillstown_user_profiles CASCADE;",
                "DROP TABLE IF EXISTS skillstown_course_details CASCADE;",
                "DROP TABLE IF EXISTS skillstown_course_quizzes CASCADE;",
                "DROP TABLE IF EXISTS skillstown_quiz_attempts CASCADE;",
                "DROP TABLE IF EXISTS students CASCADE;",
                "DROP TABLE IF EXISTS companies CASCADE;",
                "DROP TABLE IF EXISTS category CASCADE;",
                "DROP TABLE IF EXISTS skillstown_courses CASCADE;"
            ]
            for cmd in cmds: 
                db.session.execute(text(cmd))
            db.session.commit()
            db.create_all()
            flash('Tables reset successfully', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error resetting tables: {e}', 'danger')
        return redirect(get_url_for('skillstown_user_profile'))

    # Fixed learning analytics route with proper serialization
    @app.route('/course/<int:course_id>/learning-analytics')
    @login_required
    def get_learning_analytics(course_id):
        """Get detailed learning analytics for a course"""
        try:
            progress = UserLearningProgress.query.filter_by(
                user_id=current_user.id,
                course_id=str(course_id)
            ).first()
            
            recent_attempts = CourseQuizAttempt.query.filter_by(
                user_id=current_user.id
            ).join(CourseQuiz).filter(
                CourseQuiz.user_course_id == course_id
            ).order_by(CourseQuizAttempt.completed_at.desc()).limit(10).all()
            
            analytics = {
                'learningVelocity': 0,
                'consistencyScore': 0,
                'strongestAreas': [],
                'improvementAreas': [],
                'studyRecommendations': []
            }
            
            if recent_attempts:
                scores = [attempt.score for attempt in recent_attempts if attempt.score is not None]
                if len(scores) >= 2:
                    first_score = scores[-1]
                    last_score = scores[0]
                    if first_score > 0 and len(scores) > 1 :
                        analytics['learningVelocity'] = round(((last_score - first_score) / first_score) * 100)
                    elif last_score > 0 and first_score == 0:
                         analytics['learningVelocity'] = 100

                if scores:
                    mean_score = sum(scores) / len(scores)
                    variance = sum((score - mean_score) ** 2 for score in scores) / len(scores)
                    analytics['consistencyScore'] = max(0, round(100 - (variance / 25)))

            progress_data = None
            try:
                print(f"DEBUG: Learning Analytics: Original progress object before serialization: type={type(progress)}, id={(progress.id if progress else 'None')}")
                progress_data = serialize_learning_progress(progress)
                print(f"DEBUG: Learning Analytics: progress_data after serialization: type={type(progress_data)}, content={json.dumps(progress_data, indent=2) if progress_data is not None else 'None'}")
            except Exception as e_serialize:
                print(f"ERROR: Learning Analytics: Exception during serialize_learning_progress call: {e_serialize}")
                if progress:
                    print(f"DEBUG: Learning Analytics: Original progress object state during exception: id={progress.id}")
                else:
                    print("DEBUG: Learning Analytics: Original progress object was None during exception.")
                progress_data = {'error': 'Failed to serialize learning progress', 'details': str(e_serialize)}

            return jsonify({
                'progress': progress_data,
                'analytics': analytics,
                'recentAttempts': len(recent_attempts)
            })
            
        except Exception as e:
            print(f"ERROR: Error in get_learning_analytics route: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e), 'progress_fallback': {'error': 'Outer exception in get_learning_analytics'}}), 500

    # Fixed user learning progress route
    @app.route('/user/learning-progress/<course_id>')
    @login_required
    def get_user_learning_progress(course_id):
        """Get user's learning progress for a specific course"""
        try:
            progress = UserLearningProgress.query.filter_by(
                user_id=current_user.id,
                course_id=course_id
            ).first()
            
            if not progress:
                return jsonify({'error': 'No learning progress found'}), 404
            
            # Serialize progress data properly
            progress_data = serialize_learning_progress(progress)
            
            return jsonify({'progress': progress_data})
            
        except Exception as e:
            print(f"Error getting learning progress: {e}")
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500

    # Health check endpoint for self-pinging
    @app.route('/health')
    def health_check():
        """Health check endpoint for monitoring and self-pinging"""
        try:
            # Test database connection
            db.session.execute(text('SELECT 1'))
            db_status = 'healthy'
        except Exception as e:
            db_status = f'unhealthy: {str(e)}'
        
        return jsonify({
            'status': 'healthy',
            'database': db_status,
            'timestamp': datetime.utcnow().isoformat(),
            'service': 'skillstown',
            'environment': 'production' if is_production() else 'development',
            'features': {
                'quiz_integration': True,
                'podcast_generation': True,
                'learning_analytics': True,
                'self_pinging': ping_service.running if ping_service else False
            }
        })

    # Error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(413)
    def file_too_large_error(error):
        return render_template('errors/413.html'), 413

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('errors/500.html'), 500

    # Graceful shutdown handler
    @app.teardown_appcontext
    def shutdown_session(exception=None):
        db.session.remove()

    return app

if __name__ == '__main__':
    app = create_app()
    
    # Start self-pinging for production
    if is_production():
        print("🚀 Starting SkillsTown in production mode with self-pinging")
    
    app.run(debug=not is_production())
else:
    app = create_app()