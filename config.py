"""
Configuration settings for the SkillsTown CV Analyzer application.
"""

import os

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

# Prompt templates for different analysis types
SKILL_ANALYSIS_PROMPT = """
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
Return only valid JSON without markdown formatting.
"""

JOB_MATCHING_FIELDS = """
3. "job_requirements": Array of skills/requirements from the job description
4. "skill_gaps": Array of skills needed for the job but missing from CV
5. "matching_skills": Array of skills that match between CV and job
6. "career_advice": Brief advice on how to bridge the gap
"""

def get_analysis_prompt(cv_text, job_description=None):
    """Generate the appropriate prompt based on whether job description is provided"""
    if job_description and job_description.strip():
        job_desc_text = " and job description"
        job_description_section = f"\nJOB DESCRIPTION:\n{job_description[:2000]}"
        job_specific_fields = JOB_MATCHING_FIELDS
    else:
        job_desc_text = ""
        job_description_section = ""
        job_specific_fields = ""
    
    return SKILL_ANALYSIS_PROMPT.format(
        job_desc_text=job_desc_text,
        cv_text=cv_text[:4000 if not job_description else 3000],
        job_description_section=job_description_section,
        job_specific_fields=job_specific_fields
    )
DEBUG = True

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.txt'}

# Create upload directory if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Paths to data files
SKILLS_JSON_PATH = 'static/data/skills.json'
COURSE_CATALOG_PATH = 'static/data/course_catalog.json'

# Default skills list (if skills.json doesn't exist)
DEFAULT_SKILLS = [
    "python","java","javascript","html","css","sql","nosql","react","angular","node.js",
    "django","flask","php","ruby","c++","c#","swift","kotlin","machine learning","ai",
    "data analysis","data science","cloud computing","aws","azure","devops","docker",
    "kubernetes","git","blockchain","cybersecurity","project management","agile","scrum",
    "lean","six sigma","leadership","marketing","seo","content marketing","social media marketing",
    "digital marketing","sales","crm","accounting","financial analysis","budgeting","audit",
    "communication","public speaking","writing","editing","excel","word","powerpoint",
    "time management","problem solving","critical thinking"
]

# Maximum number of skills to extract
MAX_SKILLS = 20

# Maximum number of course recommendations
MAX_RECOMMENDATIONS = 10