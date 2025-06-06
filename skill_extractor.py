"""
Skill extraction module for the SkillsTown CV Analyzer application.
Updated to use Gemini API instead of spaCy for better accuracy and job matching.
"""

import json
import logging
import requests
import re
import os
from collections import Counter

logger = logging.getLogger(__name__)

# Gemini API Configuration
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1/models/gemini-2.0-flash:generateContent"

# Gemini API settings for different use cases
GEMINI_CONFIGS = {
    'skill_analysis': {
        'temperature': 0.3,
        'maxOutputTokens': 2000,
        'topP': 0.8
    },
    'course_recommendations': {
        'temperature': 0.4,
        'maxOutputTokens': 1500,
        'topP': 0.9
    },
    'career_advice': {
        'temperature': 0.5,
        'maxOutputTokens': 1000,
        'topP': 0.85
    }
}

def get_analysis_prompt(cv_text, job_description=None):
    """Generate the appropriate prompt based on whether job description is provided"""
    
    # Base prompt structure
    base_prompt = """
Analyze this CV{job_desc_text} to extract skills and provide career guidance.

CV TEXT:
{cv_text}

{job_description_section}

Please provide a JSON response with:
1. "current_skills": Array of technical and professional skills found in the CV
{job_specific_fields}
2. "skill_categories": Object categorizing skills (e.g. "programming": [...], "data": [...], "management": [...])
3. "experience_level": Estimated experience level (entry/mid/senior)
4. "learning_recommendations": Array of specific courses/skills to focus on
5. "career_paths": Array of potential career directions based on current skills

Focus on technical skills, programming languages, frameworks, tools, certifications, and professional competencies.
Return only valid JSON without markdown formatting or code blocks.
"""
    
    job_matching_fields = """
3. "job_requirements": Array of skills/requirements from the job description
4. "skill_gaps": Array of skills needed for the job but missing from CV
5. "matching_skills": Array of skills that match between CV and job
6. "career_advice": Brief advice on how to bridge the gap
"""
    
    if job_description and job_description.strip():
        job_desc_text = " and job description"
        job_description_section = f"\nJOB DESCRIPTION:\n{job_description[:2000]}"
        job_specific_fields = job_matching_fields
        cv_text_limit = 3000  # Limit CV text when we have job description
    else:
        job_desc_text = ""
        job_description_section = ""
        job_specific_fields = ""
        cv_text_limit = 4000  # Allow more CV text when no job description
    
    return base_prompt.format(
        job_desc_text=job_desc_text,
        cv_text=cv_text[:cv_text_limit],
        job_description_section=job_description_section,
        job_specific_fields=job_specific_fields
    )

class SkillExtractor:
    """
    A class to extract skills from text content using Google Gemini API.
    Provides enhanced job matching and career guidance capabilities.
    """
    
    def __init__(self, skills_path=None, default_skills=None, nlp_model=None):
        """
        Initialize the skill extractor.
        
        Args:
            skills_path (str): Path to skills JSON file (legacy, not used)
            default_skills (list): Default skills list to use as fallback.
            nlp_model (str): NLP model name (legacy, not used)
        """
        self.default_skills = default_skills or self._get_default_skills()
        
        # Check if Gemini API is available
        if not GEMINI_API_KEY:
            logger.warning("GEMINI_API_KEY not set - using fallback skill extraction")
        else:
            logger.info("Gemini API available for enhanced skill extraction")
    
    def _get_default_skills(self):
        """Get default skills list for fallback extraction"""
        return [
            "python", "java", "javascript", "html", "css", "sql", "nosql", "react", 
            "angular", "node.js", "django", "flask", "php", "ruby", "c++", "c#", 
            "swift", "kotlin", "machine learning", "ai", "data analysis", "data science", 
            "cloud computing", "aws", "azure", "devops", "docker", "kubernetes", "git", 
            "blockchain", "cybersecurity", "project management", "agile", "scrum", 
            "lean", "six sigma", "leadership", "marketing", "seo", "content marketing", 
            "social media marketing", "digital marketing", "sales", "crm", "accounting", 
            "financial analysis", "budgeting", "audit", "communication", "public speaking", 
            "writing", "editing", "excel", "word", "powerpoint", "time management", 
            "problem solving", "critical thinking", "tensorflow", "pytorch", "pandas",
            "numpy", "matplotlib", "scikit-learn", "jupyter", "tableau", "power bi",
            "mongodb", "postgresql", "mysql", "redis", "elasticsearch", "apache spark",
            "hadoop", "kafka", "jenkins", "gitlab", "github", "jira", "confluence",
            "linux", "windows", "macos", "bash", "powershell", "terraform", "ansible",
            "microservices", "rest api", "graphql", "oauth", "jwt", "ssl", "https"
        ]
    
    def extract_skills(self, text, job_description=None, max_skills=25):
        """
        Extract skills from CV text with optional job description for enhanced matching.
        
        Args:
            text (str): The CV text to extract skills from.
            job_description (str, optional): Job description for targeted analysis.
            max_skills (int): Maximum number of skills to return.
            
        Returns:
            dict: Analysis results including skills, gaps, recommendations, etc.
        """
        if not text or not text.strip():
            return self._empty_result()
        
        # Try Gemini API first
        if GEMINI_API_KEY:
            try:
                logger.info("Attempting skill extraction with Gemini API")
                result = self._extract_with_gemini(text, job_description)
                if result:
                    logger.info(f"Gemini extraction successful - found {len(result.get('current_skills', []))} skills")
                    return result
                else:
                    logger.warning("Gemini API returned empty result")
            except Exception as e:
                logger.error(f"Gemini API extraction failed: {e}")
        
        # Fallback to basic extraction
        logger.info("Using fallback skill extraction")
        return self._extract_fallback(text, max_skills)
    
    def _extract_with_gemini(self, cv_text, job_description=None):
        """
        Extract skills using Gemini API for enhanced analysis.
        
        Args:
            cv_text (str): CV text content
            job_description (str, optional): Job description text
            
        Returns:
            dict: Comprehensive analysis results
        """
        prompt = get_analysis_prompt(cv_text, job_description)
        
        headers = {"Content-Type": "application/json"}
        data = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": GEMINI_CONFIGS['skill_analysis']
        }
        
        try:
            url = f"{GEMINI_API_URL}?key={GEMINI_API_KEY}"
            response = requests.post(url, headers=headers, json=data, timeout=30)
            
            if response.status_code == 200:
                response_json = response.json()
                if 'candidates' in response_json and len(response_json['candidates']) > 0:
                    text_content = response_json['candidates'][0]['content']['parts'][0]['text']
                    
                    # Try to extract JSON from the response
                    try:
                        # Remove any markdown formatting
                        text_content = text_content.strip()
                        
                        # Find JSON in the response (it might be wrapped in markdown code blocks)
                        json_match = re.search(r'```json\s*(.*?)\s*```', text_content, re.DOTALL)
                        if json_match:
                            json_str = json_match.group(1)
                        elif text_content.startswith('```') and text_content.endswith('```'):
                            # Remove code block markers
                            json_str = re.sub(r'^```.*?\n|```$', '', text_content, flags=re.MULTILINE)
                        else:
                            # Try to find JSON block
                            json_match = re.search(r'\{.*\}', text_content, re.DOTALL)
                            if json_match:
                                json_str = json_match.group(0)
                            else:
                                json_str = text_content
                        
                        result = json.loads(json_str)
                        
                        # Validate and clean the result
                        return self._validate_gemini_result(result)
                        
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse JSON from Gemini response: {e}")
                        logger.debug(f"Response content: {text_content}")
                        return None
                else:
                    logger.error("No candidates in Gemini API response")
                    return None
            else:
                logger.error(f"Gemini API error: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.Timeout:
            logger.error("Gemini API request timed out")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Gemini API request failed: {e}")
            return None
    
    def _validate_gemini_result(self, result):
        """
        Validate and clean the result from Gemini API.
        
        Args:
            result (dict): Raw result from Gemini
            
        Returns:
            dict: Validated and cleaned result
        """
        if not isinstance(result, dict):
            logger.error("Gemini result is not a dictionary")
            return None
        
        # Ensure required fields exist with defaults
        validated = {
            'current_skills': self._clean_skills_list(result.get('current_skills', [])),
            'skill_categories': self._clean_skill_categories(result.get('skill_categories', {})),
            'experience_level': self._clean_experience_level(result.get('experience_level', 'unknown')),
            'learning_recommendations': self._clean_text_list(result.get('learning_recommendations', [])),
            'career_paths': self._clean_text_list(result.get('career_paths', []))
        }
        
        # Add job-specific fields if they exist
        if 'job_requirements' in result:
            validated.update({
                'job_requirements': self._clean_skills_list(result.get('job_requirements', [])),
                'skill_gaps': self._clean_skills_list(result.get('skill_gaps', [])),
                'matching_skills': self._clean_skills_list(result.get('matching_skills', [])),
                'career_advice': self._clean_text(result.get('career_advice', ''))
            })
        
        return validated
    
    def _clean_skills_list(self, skills_list):
        """
        Clean and validate a list of skills.
        
        Args:
            skills_list (list): Raw skills list
            
        Returns:
            list: Cleaned skills list
        """
        if not isinstance(skills_list, list):
            return []
        
        cleaned = []
        seen = set()
        
        for skill in skills_list:
            if isinstance(skill, str) and skill.strip():
                # Clean the skill name
                clean_skill = skill.strip()
                
                # Basic cleaning - remove extra spaces, normalize case
                clean_skill = ' '.join(clean_skill.split())
                
                # Skip very long entries (likely not skills)
                if len(clean_skill) > 50:
                    continue
                    
                # Skip very short entries (likely not meaningful)
                if len(clean_skill) < 2:
                    continue
                
                # Convert to title case for consistency, but preserve known acronyms
                if clean_skill.upper() in ['SQL', 'HTML', 'CSS', 'API', 'REST', 'JSON', 'XML', 'AWS', 'GCP', 'CI/CD', 'AI', 'ML', 'UI', 'UX']:
                    clean_skill = clean_skill.upper()
                elif clean_skill.lower() in ['javascript', 'python', 'java', 'react', 'angular', 'vue.js', 'node.js']:
                    # Keep common tech names in their standard case
                    case_map = {
                        'javascript': 'JavaScript',
                        'python': 'Python',
                        'java': 'Java',
                        'react': 'React',
                        'angular': 'Angular',
                        'vue.js': 'Vue.js',
                        'node.js': 'Node.js'
                    }
                    clean_skill = case_map.get(clean_skill.lower(), clean_skill.title())
                else:
                    clean_skill = clean_skill.title()
                
                # Avoid duplicates (case-insensitive)
                if clean_skill.lower() not in seen:
                    cleaned.append(clean_skill)
                    seen.add(clean_skill.lower())
        
        return cleaned[:25]  # Limit to reasonable number
    
    def _clean_skill_categories(self, categories):
        """
        Clean and validate skill categories.
        
        Args:
            categories (dict): Raw categories dict
            
        Returns:
            dict: Cleaned categories
        """
        if not isinstance(categories, dict):
            return {}
        
        cleaned = {}
        for category, skills in categories.items():
            if isinstance(category, str) and isinstance(skills, list):
                clean_category = category.strip().lower().replace(' ', '_')
                clean_skills = self._clean_skills_list(skills)
                if clean_skills:  # Only include categories with skills
                    cleaned[clean_category] = clean_skills
        
        return cleaned
    
    def _clean_experience_level(self, level):
        """
        Clean and validate experience level.
        
        Args:
            level (str): Raw experience level
            
        Returns:
            str: Cleaned experience level
        """
        if not isinstance(level, str):
            return 'unknown'
        
        level = level.strip().lower()
        valid_levels = ['entry', 'junior', 'mid', 'middle', 'senior', 'lead', 'principal']
        
        # Map common variations
        level_map = {
            'junior': 'entry',
            'middle': 'mid',
            'lead': 'senior',
            'principal': 'senior'
        }
        
        level = level_map.get(level, level)
        
        return level if level in ['entry', 'mid', 'senior'] else 'unknown'
    
    def _clean_text_list(self, text_list):
        """
        Clean a list of text items (recommendations, career paths, etc.)
        
        Args:
            text_list (list): Raw text list
            
        Returns:
            list: Cleaned text list
        """
        if not isinstance(text_list, list):
            return []
        
        cleaned = []
        for item in text_list:
            if isinstance(item, str) and item.strip():
                clean_item = item.strip()
                # Remove excessive length items
                if len(clean_item) <= 200:
                    cleaned.append(clean_item)
        
        return cleaned[:10]  # Reasonable limit
    
    def _clean_text(self, text):
        """
        Clean a single text item.
        
        Args:
            text (str): Raw text
            
        Returns:
            str: Cleaned text
        """
        if not isinstance(text, str):
            return ''
        
        return text.strip()[:500]  # Limit length
    
    def _extract_fallback(self, text, max_skills=20):
        """
        Fallback skill extraction using pattern matching.
        
        Args:
            text (str): CV text
            max_skills (int): Maximum skills to return
            
        Returns:
            dict: Basic analysis result
        """
        text_lower = text.lower()
        
        # Enhanced skill patterns
        skill_patterns = [
            # Programming languages
            r'\b(?:Python|Java|JavaScript|TypeScript|C\+\+|C#|PHP|Ruby|Swift|Kotlin|Go|Rust|Scala|R|MATLAB)\b',
            # Web technologies
            r'\b(?:HTML|CSS|React|Angular|Vue\.js|Node\.js|Express|Django|Flask|Spring|Laravel|Ruby on Rails)\b',
            # Databases
            r'\b(?:SQL|MySQL|PostgreSQL|MongoDB|SQLite|Oracle|Redis|Cassandra|DynamoDB|Neo4j)\b',
            # Cloud and DevOps
            r'\b(?:Git|Docker|Kubernetes|AWS|Azure|GCP|Jenkins|CI/CD|DevOps|Terraform|Ansible)\b',
            # Data Science and AI
            r'\b(?:Machine Learning|AI|Data Science|Analytics|TensorFlow|PyTorch|Pandas|NumPy|Scikit-learn)\b',
            # Management and Soft Skills
            r'\b(?:Project Management|Agile|Scrum|Leadership|Communication|Teamwork|Problem Solving)\b',
            # Systems and Tools
            r'\b(?:Linux|Windows|macOS|Unix|Shell|Bash|PowerShell|Vim|IntelliJ|Visual Studio)\b',
            # API and Architecture
            r'\b(?:REST|API|GraphQL|Microservices|SOA|JSON|XML|SOAP|gRPC)\b',
            # Testing and Quality
            r'\b(?:Unit Testing|Integration Testing|Test Automation|Selenium|Jest|JUnit|PyTest)\b',
            # Business and Analytics Tools
            r'\b(?:Excel|PowerPoint|Tableau|Power BI|Salesforce|JIRA|Confluence|Slack)\b'
        ]
        
        skill_counter = Counter()
        
        # Extract skills using patterns
        for pattern in skill_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                skill = match.group().strip()
                # Normalize common variations
                skill_normalized = self._normalize_skill_name(skill)
                skill_counter[skill_normalized] += 1
        
        # Also check against default skills list
        for skill in self.default_skills:
            skill_variations = [skill, skill.replace(' ', ''), skill.replace(' ', '.')]
            for variation in skill_variations:
                if variation.lower() in text_lower:
                    normalized = self._normalize_skill_name(skill)
                    skill_counter[normalized] += 1
                    break
        
        # Get most common skills
        top_skills = [skill for skill, _ in skill_counter.most_common(max_skills)]
        
        # Categorize skills
        categories = self._categorize_skills(top_skills)
        
        # Estimate experience level
        experience_level = self._estimate_experience_level(text_lower, len(top_skills))
        
        # Generate basic recommendations
        recommendations = self._generate_basic_recommendations(top_skills, categories)
        
        return {
            'current_skills': top_skills,
            'skill_categories': categories,
            'experience_level': experience_level,
            'learning_recommendations': recommendations,
            'career_paths': self._suggest_career_paths(categories)
        }
    
    def _normalize_skill_name(self, skill):
        """
        Normalize skill names for consistency.
        
        Args:
            skill (str): Raw skill name
            
        Returns:
            str: Normalized skill name
        """
        skill = skill.strip()
        
        # Common normalizations
        normalizations = {
            'javascript': 'JavaScript',
            'typescript': 'TypeScript',
            'python': 'Python',
            'java': 'Java',
            'c++': 'C++',
            'c#': 'C#',
            'html': 'HTML',
            'css': 'CSS',
            'sql': 'SQL',
            'aws': 'AWS',
            'gcp': 'GCP',
            'api': 'API',
            'rest': 'REST API',
            'json': 'JSON',
            'xml': 'XML',
            'ai': 'AI',
            'ml': 'Machine Learning',
            'react': 'React',
            'angular': 'Angular',
            'vue.js': 'Vue.js',
            'node.js': 'Node.js'
        }
        
        return normalizations.get(skill.lower(), skill.title())
    
    def _categorize_skills(self, skills):
        """
        Categorize skills into different domains.
        
        Args:
            skills (list): List of skills
            
        Returns:
            dict: Categorized skills
        """
        categories = {
            'programming': [],
            'web_development': [],
            'data_science': [],
            'cloud_devops': [],
            'databases': [],
            'management': [],
            'tools': []
        }
        
        # Categorization patterns
        category_patterns = {
            'programming': [
                'python', 'java', 'javascript', 'typescript', 'c++', 'c#', 'php', 'ruby', 
                'swift', 'kotlin', 'go', 'rust', 'scala', 'r', 'matlab'
            ],
            'web_development': [
                'html', 'css', 'react', 'angular', 'vue.js', 'node.js', 'express', 
                'django', 'flask', 'spring', 'laravel', 'ruby on rails'
            ],
            'data_science': [
                'machine learning', 'ai', 'data science', 'analytics', 'tensorflow', 
                'pytorch', 'pandas', 'numpy', 'scikit-learn', 'tableau', 'power bi'
            ],
            'cloud_devops': [
                'aws', 'azure', 'gcp', 'docker', 'kubernetes', 'devops', 'ci/cd', 
                'jenkins', 'terraform', 'ansible'
            ],
            'databases': [
                'sql', 'mysql', 'postgresql', 'mongodb', 'sqlite', 'oracle', 'redis',
                'cassandra', 'dynamodb', 'neo4j'
            ],
            'management': [
                'project management', 'agile', 'scrum', 'leadership', 'communication', 
                'teamwork', 'problem solving'
            ],
            'tools': [
                'git', 'linux', 'windows', 'shell', 'bash', 'rest api', 'json', 'xml',
                'excel', 'jira', 'confluence', 'selenium', 'junit'
            ]
        }
        
        for skill in skills:
            skill_lower = skill.lower()
            categorized = False
            
            for category, patterns in category_patterns.items():
                for pattern in patterns:
                    if pattern in skill_lower or skill_lower in pattern:
                        categories[category].append(skill)
                        categorized = True
                        break
                if categorized:
                    break
            
            if not categorized:
                categories['tools'].append(skill)
        
        # Remove empty categories
        return {k: v for k, v in categories.items() if v}
    
    def _estimate_experience_level(self, text, skill_count):
        """
        Estimate experience level based on text content and skill count.
        
        Args:
            text (str): CV text (lowercase)
            skill_count (int): Number of skills found
            
        Returns:
            str: Experience level
        """
        # Look for experience indicators
        senior_indicators = [
            'senior', 'lead', 'principal', 'architect', 'manager', 'director',
            'team lead', 'tech lead', 'head of', 'vp ', 'cto', 'cio'
        ]
        mid_indicators = [
            'experience', 'years', 'developed', 'led', 'managed', 'designed',
            'implemented', 'built', 'created', 'delivered'
        ]
        
        # Count experience indicators
        senior_count = sum(1 for indicator in senior_indicators if indicator in text)
        mid_count = sum(1 for indicator in mid_indicators if indicator in text)
        
        # Look for years of experience
        years_match = re.search(r'(\d+)[\s\-]*(?:years?|yrs?)', text)
        years_experience = int(years_match.group(1)) if years_match else 0
        
        # Determine experience level
        if senior_count >= 2 or years_experience >= 8 or skill_count >= 20:
            return 'senior'
        elif mid_count >= 3 or years_experience >= 3 or skill_count >= 10:
            return 'mid'
        else:
            return 'entry'
    
    def _generate_basic_recommendations(self, skills, categories):
        """
        Generate basic learning recommendations.
        
        Args:
            skills (list): Current skills
            categories (dict): Categorized skills
            
        Returns:
            list: Learning recommendations
        """
        recommendations = []
        
        # Programming recommendations
        if 'programming' in categories:
            prog_skills = [s.lower() for s in categories['programming']]
            if 'python' in prog_skills:
                recommendations.append("Advanced Python concepts like decorators, async programming, and design patterns")
            if 'javascript' in prog_skills:
                recommendations.append("Modern JavaScript frameworks and ES6+ features, TypeScript")
            if 'java' in prog_skills:
                recommendations.append("Spring Boot, microservices architecture, and advanced Java concepts")
        
        # Web development recommendations
        if 'web_development' in categories:
            recommendations.append("Full-stack development with modern frameworks and RESTful API design")
            recommendations.append("Progressive Web Apps (PWA) and modern deployment strategies")
        
        # Data science recommendations
        if 'data_science' in categories:
            recommendations.append("Advanced machine learning algorithms, deep learning with neural networks")
            recommendations.append("Data engineering, MLOps, and production-ready ML systems")
        
        # Cloud/DevOps recommendations
        if 'cloud_devops' in categories:
            recommendations.append("Container orchestration, serverless architecture, and Infrastructure as Code")
            recommendations.append("Site reliability engineering (SRE) and advanced CI/CD practices")
        
        # Database recommendations
        if 'databases' in categories:
            recommendations.append("Database optimization, NoSQL design patterns, and data modeling")
        
        # Management recommendations
        if 'management' in categories:
            recommendations.append("Technical leadership, system design, and cross-functional collaboration")
        
        # General recommendations based on skill count
        if len(skills) < 5:
            recommendations.extend([
                "Build a strong foundation in programming fundamentals and computer science concepts",
                "Learn version control with Git and collaborative development practices",
                "Develop problem-solving skills through coding challenges and projects"
            ])
        elif len(skills) >= 15:
            recommendations.extend([
                "Focus on system design and architecture patterns for scalable applications",
                "Develop expertise in emerging technologies like AI/ML or blockchain",
                "Consider technical leadership and mentoring opportunities"
            ])
        
        return recommendations[:8]  # Limit to top 8
    
    def _suggest_career_paths(self, categories):
        """
        Suggest career paths based on skill categories.
        
        Args:
            categories (dict): Categorized skills
            
        Returns:
            list: Career path suggestions
        """
        paths = []
        
        if 'programming' in categories and 'web_development' in categories:
            paths.append("Full-Stack Web Developer")
        
        if 'data_science' in categories:
            if 'programming' in categories:
                paths.append("Data Scientist / Machine Learning Engineer")
            else:
                paths.append("Data Analyst / Business Intelligence Specialist")
        
        if 'cloud_devops' in categories:
            paths.append("DevOps Engineer / Site Reliability Engineer")
            paths.append("Cloud Solutions Architect")
        
        if 'management' in categories and len(categories) > 2:
            paths.append("Technical Project Manager / Engineering Manager")
        
        if 'programming' in categories:
            paths.append("Software Engineer / Backend Developer")
            paths.append("Systems Architect / Technical Lead")
        
        if 'web_development' in categories:
            paths.append("Frontend Developer / UI/UX Developer")
        
        if 'databases' in categories and 'programming' in categories:
            paths.append("Database Developer / Data Engineer")
        
        # Default paths if none match
        if not paths:
            paths = [
                "Software Developer",
                "IT Specialist",
                "Technical Analyst",
                "Systems Administrator"
            ]
        
        return paths[:5]  # Limit to top 5
    
    def _empty_result(self):
        """Return empty result structure"""
        return {
            'current_skills': [],
            'skill_categories': {},
            'experience_level': 'unknown',
            'learning_recommendations': ['Please upload a CV with detailed skills and experience information'],
            'career_paths': ['Software Developer', 'IT Specialist']
        }

# Convenience functions for backward compatibility
def extract_skills_from_text(text, job_description=None):
    """
    Extract skills from text using the SkillExtractor class.
    
    Args:
        text (str): CV text content
        job_description (str, optional): Job description for matching
        
    Returns:
        list: List of extracted skills (for backward compatibility)
    """
    extractor = SkillExtractor()
    result = extractor.extract_skills(text, job_description)
    return result.get('current_skills', [])

def analyze_skills_with_gemini(cv_text, job_description=None):
    """
    Analyze skills using Gemini API with job description matching.
    
    Args:
        cv_text (str): CV text content
        job_description (str, optional): Job description for matching
        
    Returns:
        dict: Complete analysis results
    """
    extractor = SkillExtractor()
    return extractor.extract_skills(cv_text, job_description)