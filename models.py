from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
import uuid

db = SQLAlchemy()

class Company(db.Model):
    __tablename__ = 'companies'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(255), nullable=False)
    industry = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    
    # Relationship to students
    students = db.relationship('Student', backref='company', lazy=True)
    
    def __repr__(self):
        return f'<Company {self.name}>'

class Student(db.Model, UserMixin):
    __tablename__ = 'students'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True)
    enrolled_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    company_id = db.Column(db.String(36), db.ForeignKey('companies.id'), nullable=True)
    
    # For Flask-Login compatibility
    username = db.Column(db.String(255))
    password_hash = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True)
    date_joined = db.Column(db.DateTime, default=db.func.current_timestamp())
    
    # NEW: Quiz system UUID for integration with external quiz API
    quiz_user_uuid = db.Column(db.String(36), nullable=True, unique=True)
    
    # Relationships
    enrollments = db.relationship('Course', backref='student', lazy=True)
    profiles = db.relationship('UserProfile', backref='student', lazy=True)
    
    def get_id(self):
        return str(self.id)
    
    def get_quiz_uuid(self):
        """Get or create quiz UUID for this user"""
        if not self.quiz_user_uuid:
            self.quiz_user_uuid = str(uuid.uuid4())
            db.session.commit()
        return self.quiz_user_uuid
    
    @property
    def is_authenticated(self):
        return True
    
    @property
    def is_anonymous(self):
        return False
    
    def __repr__(self):
        return f'<Student {self.name}>'

class Category(db.Model):
    __tablename__ = 'category'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    
    # Relationships
    content_pages = db.relationship('ContentPage', backref='category', lazy=True)
    courses = db.relationship('Course', backref='category_rel', lazy=True)
    
    def __repr__(self):
        return f'<Category {self.name}>'

class ContentPage(db.Model):
    __tablename__ = 'content_pages'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    category_id = db.Column(db.String(36), db.ForeignKey('category.id'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text)  # JSON format for rich content
    is_draft = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    
    def __repr__(self):
        return f'<ContentPage {self.title}>'

class Course(db.Model):
    __tablename__ = 'courses'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = db.Column(db.String(36), db.ForeignKey('students.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    category_id = db.Column(db.String(36), db.ForeignKey('category.id'), nullable=False)
    published = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    
    # Status and progress tracking
    status = db.Column(db.String(50), default='enrolled')  # enrolled, in_progress, completed
    progress_percentage = db.Column(db.Integer, default=0)
    completed_at = db.Column(db.DateTime)
    
    def __repr__(self):
        return f'<Course {self.name}>'

class CourseContentPage(db.Model):
    __tablename__ = 'courses_content_pages'
    
    course_id = db.Column(db.String(36), db.ForeignKey('courses.id'), primary_key=True)
    content_page_id = db.Column(db.String(36), db.ForeignKey('content_pages.id'), primary_key=True)
    order_index = db.Column(db.Integer, nullable=False)
    is_required = db.Column(db.Boolean, default=True)
    
    # Relationships
    course = db.relationship('Course', backref=db.backref('course_content_pages', lazy=True))
    content_page = db.relationship('ContentPage', backref=db.backref('course_content_pages', lazy=True))
    
    def __repr__(self):
        return f'<CourseContentPage {self.course_id}:{self.content_page_id}>'

class UserProfile(db.Model):
    __tablename__ = 'skillstown_user_profiles'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('students.id'), nullable=False)
    cv_text = db.Column(db.Text)
    job_description = db.Column(db.Text)
    skills = db.Column(db.Text)
    skill_analysis = db.Column(db.Text)
    uploaded_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    
    def __repr__(self):
        return f'<UserProfile {self.user_id}>'

class CourseDetail(db.Model):
    """Extended course details for existing UserCourse entries"""
    __tablename__ = 'skillstown_course_details'
    
    id = db.Column(db.Integer, primary_key=True)
    user_course_id = db.Column(db.Integer, db.ForeignKey('skillstown_user_courses.id'), nullable=False)  # References UserCourse.id
    description = db.Column(db.Text)
    progress_percentage = db.Column(db.Integer, default=0)
    completed_at = db.Column(db.DateTime)
    materials = db.Column(db.Text)  # JSON format for course materials
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    # New field for quiz results
    quiz_results = db.Column(db.Text)  # JSON string containing quiz performance and recommendations
    # Relationship to UserCourse
    user_course = db.relationship('UserCourse', backref='details')
    
    def __repr__(self):
        return f'<CourseDetail {self.user_course_id}>'

class UserCourse(db.Model):
    __tablename__ = 'skillstown_user_courses'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('students.id'), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    course_name = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(50), default='enrolled')
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    __table_args__ = (db.UniqueConstraint('user_id', 'course_name', name='skillstown_user_course_unique'),)

    def __repr__(self):
        return f'<UserCourse {self.course_name}>'

class SkillsTownCourse(db.Model):
    __tablename__ = 'skillstown_courses'
    
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    url = db.Column(db.String(500))
    provider = db.Column(db.String(100), default='SkillsTown')
    skills_taught = db.Column(db.Text)
    difficulty_level = db.Column(db.String(20))
    duration = db.Column(db.String(50))
    keywords = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    
    def __repr__(self):
        return f'<SkillsTownCourse {self.name}>'

# NEW: Model to track quiz instances created for courses
class CourseQuiz(db.Model):
    __tablename__ = 'skillstown_course_quizzes'
    
    id = db.Column(db.Integer, primary_key=True)
    user_course_id = db.Column(db.Integer, db.ForeignKey('skillstown_user_courses.id'), nullable=False)
    quiz_api_id = db.Column(db.String(100), nullable=False)  # ID from the quiz API
    quiz_title = db.Column(db.String(255))
    quiz_description = db.Column(db.Text)
    questions_count = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    
    # Relationship to UserCourse
    user_course = db.relationship('UserCourse', backref='quizzes')
    
    def __repr__(self):
        return f'<CourseQuiz {self.quiz_api_id}>'

class CourseQuizAttempt(db.Model):
    __tablename__ = 'skillstown_quiz_attempts'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('students.id'), nullable=False)
    course_quiz_id = db.Column(db.Integer, db.ForeignKey('skillstown_course_quizzes.id'), nullable=False)
    course_id = db.Column(db.Integer, nullable=True)  # Direct course_id for easier tracking
    attempt_api_id = db.Column(db.String(100), nullable=False)  # ID from the quiz API
    score = db.Column(db.Integer)
    total_questions = db.Column(db.Integer)
    correct_answers = db.Column(db.Integer)
    feedback_strengths = db.Column(db.Text)
    feedback_improvements = db.Column(db.Text)
    user_answers = db.Column(db.Text)  # JSON array of user answers
    completed_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    
    # Relationships
    user = db.relationship('Student', backref='quiz_attempts')
    course_quiz = db.relationship('CourseQuiz', backref='attempts')
    
class UserLearningProgress(db.Model):
    __tablename__ = 'skillstown_user_learning_progress'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('students.id'), nullable=False)
    course_id = db.Column(db.String(50), nullable=False)
    knowledge_areas = db.Column(db.Text)  # JSON string
    weak_areas = db.Column(db.Text)  # JSON array
    strong_areas = db.Column(db.Text)  # JSON array
    recommended_topics = db.Column(db.Text)  # JSON array
    learning_curve = db.Column(db.Text)  # JSON array
    overall_progress = db.Column(db.Integer, default=0)
    mastery_level = db.Column(db.String(20), default='beginner')
    last_updated = db.Column(db.DateTime, default=db.func.current_timestamp())
    
    __table_args__ = (db.UniqueConstraint('user_id', 'course_id', name='unique_user_course_progress'),)
    
    def __repr__(self):
        return f'<UserLearningProgress {self.user_id}:{self.course_id}>'
    def __repr__(self):
        return f'<CourseQuizAttempt {self.attempt_api_id}>'