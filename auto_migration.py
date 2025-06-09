#!/usr/bin/env python3
"""
Enhanced auto_migration.py - Handles missing columns in existing tables
"""

import os
import logging
from sqlalchemy import create_engine, text, inspect

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_database_url():
    """Get database URL from environment"""
    db_url = os.environ.get('DATABASE_URL')
    if db_url and db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql://')
    return db_url

def check_and_add_column(conn, table_name, column_name, column_definition):
    """Check if column exists and add it if it doesn't"""
    try:
        inspector = inspect(conn)
        
        # Check if table exists first
        existing_tables = inspector.get_table_names()
        if table_name not in existing_tables:
            logger.info(f"Table {table_name} doesn't exist - skipping column check")
            return False
            
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        
        if column_name not in columns:
            logger.info(f"Adding missing column {column_name} to {table_name}")
            conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"))
            return True
        else:
            logger.info(f"Column {column_name} already exists in {table_name}")
            return False
    except Exception as e:
        logger.error(f"Error checking/adding column {column_name} to {table_name}: {e}")
        return False

def create_table_if_not_exists(conn, table_name, create_sql):
    """Create table if it doesn't exist"""
    try:
        inspector = inspect(conn)
        existing_tables = inspector.get_table_names()
        
        if table_name not in existing_tables:
            logger.info(f"Creating missing table {table_name}")
            conn.execute(text(create_sql))
            return True
        else:
            logger.info(f"Table {table_name} already exists")
            return False
    except Exception as e:
        logger.error(f"Error creating table {table_name}: {e}")
        return False

def run_auto_migration():
    """Run automatic database migration"""
    db_url = get_database_url()
    
    if not db_url:
        logger.warning("No DATABASE_URL found - skipping migration")
        return False
    
    logger.info("Starting automatic database migration...")
    
    try:
        engine = create_engine(db_url)
        
        with engine.connect() as conn:
            trans = conn.begin()
            
            try:
                changes_made = False
                
                # 1. Add quiz_user_uuid column to students table
                if check_and_add_column(conn, 'students', 'quiz_user_uuid', 'VARCHAR(36) UNIQUE'):
                    changes_made = True
                
                # 2. Create skillstown_user_courses table
                skillstown_user_courses_sql = """
                    CREATE TABLE skillstown_user_courses (
                        id SERIAL PRIMARY KEY,
                        user_id VARCHAR(36) NOT NULL REFERENCES students(id) ON DELETE CASCADE,
                        category VARCHAR(100) NOT NULL,
                        course_name VARCHAR(255) NOT NULL,
                        status VARCHAR(50) DEFAULT 'enrolled',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        CONSTRAINT skillstown_user_course_unique UNIQUE (user_id, course_name)
                    )
                """
                if create_table_if_not_exists(conn, 'skillstown_user_courses', skillstown_user_courses_sql):
                    changes_made = True
                
                # 3. Create skillstown_course_details table
                skillstown_course_details_sql = """
                    CREATE TABLE skillstown_course_details (
                        id SERIAL PRIMARY KEY,
                        user_course_id INTEGER NOT NULL REFERENCES skillstown_user_courses(id) ON DELETE CASCADE,
                        description TEXT,
                        progress_percentage INTEGER DEFAULT 0,
                        completed_at TIMESTAMP,
                        materials TEXT,
                        quiz_results TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """
                if create_table_if_not_exists(conn, 'skillstown_course_details', skillstown_course_details_sql):
                    changes_made = True
                
                # 3b. Add quiz_results column to existing skillstown_course_details table
                if check_and_add_column(conn, 'skillstown_course_details', 'quiz_results', 'TEXT'):
                    changes_made = True
                
                # 4. Create skillstown_user_profiles table
                skillstown_user_profiles_sql = """
                    CREATE TABLE skillstown_user_profiles (
                        id SERIAL PRIMARY KEY,
                        user_id VARCHAR(36) NOT NULL REFERENCES students(id),
                        cv_text TEXT,
                        job_description TEXT,
                        skills TEXT,
                        skill_analysis TEXT,
                        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """
                if create_table_if_not_exists(conn, 'skillstown_user_profiles', skillstown_user_profiles_sql):
                    changes_made = True
                
                # 5. Create skillstown_course_quizzes table
                skillstown_course_quizzes_sql = """
                    CREATE TABLE skillstown_course_quizzes (
                        id SERIAL PRIMARY KEY,
                        user_course_id INTEGER NOT NULL REFERENCES skillstown_user_courses(id) ON DELETE CASCADE,
                        quiz_api_id VARCHAR(100) NOT NULL,
                        quiz_title VARCHAR(255),
                        quiz_description TEXT,
                        questions_count INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """
                if create_table_if_not_exists(conn, 'skillstown_course_quizzes', skillstown_course_quizzes_sql):
                    changes_made = True
                
                # 6. Create skillstown_quiz_attempts table
                skillstown_quiz_attempts_sql = """
                    CREATE TABLE skillstown_quiz_attempts (
                        id SERIAL PRIMARY KEY,
                        user_id VARCHAR(36) NOT NULL REFERENCES students(id) ON DELETE CASCADE,
                        course_quiz_id INTEGER NOT NULL REFERENCES skillstown_course_quizzes(id) ON DELETE CASCADE,
                        attempt_api_id VARCHAR(100) NOT NULL,
                        score INTEGER,
                        total_questions INTEGER,
                        correct_answers INTEGER,
                        feedback_strengths TEXT,
                        feedback_improvements TEXT,
                        user_answers TEXT,
                        completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """
                if create_table_if_not_exists(conn, 'skillstown_quiz_attempts', skillstown_quiz_attempts_sql):
                    changes_made = True
                
                # 7. Create skillstown_user_learning_progress table
                skillstown_user_learning_progress_sql = """
                    CREATE TABLE skillstown_user_learning_progress (
                        id SERIAL PRIMARY KEY,
                        user_id VARCHAR(36) NOT NULL REFERENCES students(id),
                        course_id VARCHAR(50) NOT NULL,
                        knowledge_areas TEXT DEFAULT '{}',
                        weak_areas TEXT DEFAULT '[]',
                        strong_areas TEXT DEFAULT '[]',
                        recommended_topics TEXT DEFAULT '[]',
                        learning_curve TEXT DEFAULT '[]',
                        overall_progress INTEGER DEFAULT 0,
                        mastery_level VARCHAR(20) DEFAULT 'beginner',
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        CONSTRAINT unique_user_course_progress UNIQUE (user_id, course_id)
                    )
                """
                if create_table_if_not_exists(conn, 'skillstown_user_learning_progress', skillstown_user_learning_progress_sql):
                    changes_made = True
                
                # 8. Check and add any other missing columns to existing tables
                
                # Check skillstown_user_courses for any missing columns
                user_courses_columns = [
                    ('status', 'VARCHAR(50) DEFAULT \'enrolled\''),
                    ('created_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
                ]
                
                for col_name, col_def in user_courses_columns:
                    if check_and_add_column(conn, 'skillstown_user_courses', col_name, col_def):
                        changes_made = True
                
                # Check skillstown_course_details for any missing columns
                course_details_columns = [
                    ('progress_percentage', 'INTEGER DEFAULT 0'),
                    ('completed_at', 'TIMESTAMP'),
                    ('materials', 'TEXT'),
                    ('created_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
                ]
                
                for col_name, col_def in course_details_columns:
                    if check_and_add_column(conn, 'skillstown_course_details', col_name, col_def):
                        changes_made = True
                
                # Check skillstown_quiz_attempts for missing columns
                quiz_attempts_columns = [
                    ('course_quiz_id', 'INTEGER REFERENCES skillstown_course_quizzes(id) ON DELETE CASCADE'),
                    ('score', 'INTEGER'),
                    ('total_questions', 'INTEGER'),
                    ('correct_answers', 'INTEGER'),
                    ('feedback_strengths', 'TEXT'),
                    ('feedback_improvements', 'TEXT'),
                    ('user_answers', 'TEXT'),
                    ('completed_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
                ]
                
                for col_name, col_def in quiz_attempts_columns:
                    if check_and_add_column(conn, 'skillstown_quiz_attempts', col_name, col_def):
                        changes_made = True
                
                # Commit all changes
                trans.commit()
                
                if changes_made:
                    logger.info("✅ Database migration completed successfully!")
                else:
                    logger.info("✅ Database schema is up to date - no changes needed")
                
                return True
                
            except Exception as e:
                trans.rollback()
                logger.error(f"❌ Migration failed: {e}")
                import traceback
                traceback.print_exc()
                return False
                
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        return False

if __name__ == '__main__':
    run_auto_migration()