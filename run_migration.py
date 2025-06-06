#!/usr/bin/env python3
"""
Fixed database migration script for PostgreSQL
This will properly add the quiz_user_uuid column and create quiz tables
"""

import os
import sys
from sqlalchemy import create_engine, text

def get_database_url():
    """Get database URL from environment"""
    db_url = os.environ.get('DATABASE_URL')
    if db_url and db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql://')
    return db_url or 'sqlite:///skillstown.db'

def run_quiz_migration():
    """Run the quiz integration database migration"""
    
    print("🗄️  Running Quiz Integration Database Migration...")
    print("=" * 50)
    
    db_url = get_database_url()
    print(f"Database URL: {db_url}")
    
    engine = create_engine(db_url)
    
    try:
        with engine.connect() as conn:
            # Start transaction
            trans = conn.begin()
            
            try:
                # Step 1: Check if quiz_user_uuid column exists
                print("📝 Checking if quiz_user_uuid column exists...")
                
                if 'postgresql' in db_url:
                    # PostgreSQL
                    result = conn.execute(text("""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name='students' 
                        AND column_name='quiz_user_uuid'
                    """))
                else:
                    # SQLite
                    result = conn.execute(text("PRAGMA table_info(students)"))
                
                column_exists = result.fetchone() is not None
                
                if not column_exists:
                    print("➕ Adding quiz_user_uuid column to students table...")
                    
                    if 'postgresql' in db_url:
                        # PostgreSQL syntax
                        conn.execute(text("""
                            ALTER TABLE students 
                            ADD COLUMN quiz_user_uuid VARCHAR(36)
                        """))
                        
                        # Add unique constraint
                        conn.execute(text("""
                            ALTER TABLE students 
                            ADD CONSTRAINT students_quiz_user_uuid_unique 
                            UNIQUE (quiz_user_uuid)
                        """))
                    else:
                        # SQLite syntax
                        conn.execute(text("""
                            ALTER TABLE students 
                            ADD COLUMN quiz_user_uuid TEXT UNIQUE
                        """))
                    
                    print("✅ Successfully added quiz_user_uuid column")
                else:
                    print("✅ quiz_user_uuid column already exists")
                
                # Step 2: Create CourseQuiz table
                print("📝 Creating skillstown_course_quizzes table...")
                
                if 'postgresql' in db_url:
                    # PostgreSQL syntax
                    conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS skillstown_course_quizzes (
                            id SERIAL PRIMARY KEY,
                            user_course_id INTEGER NOT NULL,
                            quiz_api_id VARCHAR(100) NOT NULL,
                            quiz_title VARCHAR(255),
                            quiz_description TEXT,
                            questions_count INTEGER,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (user_course_id) REFERENCES skillstown_user_courses(id) ON DELETE CASCADE
                        )
                    """))
                else:
                    # SQLite syntax
                    conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS skillstown_course_quizzes (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_course_id INTEGER NOT NULL,
                            quiz_api_id VARCHAR(100) NOT NULL,
                            quiz_title VARCHAR(255),
                            quiz_description TEXT,
                            questions_count INTEGER,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (user_course_id) REFERENCES skillstown_user_courses(id) ON DELETE CASCADE
                        )
                    """))
                
                print("✅ Successfully created skillstown_course_quizzes table")
                
                # Step 3: Create CourseQuizAttempt table
                print("📝 Creating skillstown_quiz_attempts table...")
                
                if 'postgresql' in db_url:
                    # PostgreSQL syntax
                    conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS skillstown_quiz_attempts (
                            id SERIAL PRIMARY KEY,
                            user_id VARCHAR(36) NOT NULL,
                            course_quiz_id INTEGER NOT NULL,
                            attempt_api_id VARCHAR(100) NOT NULL,
                            score INTEGER,
                            total_questions INTEGER,
                            correct_answers INTEGER,
                            feedback_strengths TEXT,
                            feedback_improvements TEXT,
                            user_answers TEXT,
                            completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (user_id) REFERENCES students(id) ON DELETE CASCADE,
                            FOREIGN KEY (course_quiz_id) REFERENCES skillstown_course_quizzes(id) ON DELETE CASCADE
                        )
                    """))
                else:
                    # SQLite syntax
                    conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS skillstown_quiz_attempts (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id VARCHAR(36) NOT NULL,
                            course_quiz_id INTEGER NOT NULL,
                            attempt_api_id VARCHAR(100) NOT NULL,
                            score INTEGER,
                            total_questions INTEGER,
                            correct_answers INTEGER,
                            feedback_strengths TEXT,
                            feedback_improvements TEXT,
                            user_answers TEXT,
                            completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (user_id) REFERENCES students(id) ON DELETE CASCADE,
                            FOREIGN KEY (course_quiz_id) REFERENCES skillstown_course_quizzes(id) ON DELETE CASCADE
                        )
                    """))
                
                print("✅ Successfully created skillstown_quiz_attempts table")
                
                # Commit the transaction
                trans.commit()
                print("\n🎉 Quiz integration migration completed successfully!")
                print("Your SkillsTown application now supports AI quiz generation and assessment.")
                
                return True
                
            except Exception as e:
                trans.rollback()
                print(f"❌ Migration failed: {e}")
                return False
                
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

def test_migration():
    """Test if the migration was successful"""
    print("\n🔍 Testing migration...")
    
    db_url = get_database_url()
    engine = create_engine(db_url)
    
    try:
        with engine.connect() as conn:
            # Test if tables exist and have correct structure
            tables_to_check = [
                'students',
                'skillstown_course_quizzes', 
                'skillstown_quiz_attempts'
            ]
            
            for table in tables_to_check:
                try:
                    result = conn.execute(text(f"SELECT COUNT(*) FROM {table} LIMIT 1"))
                    print(f"✅ {table} table exists and is accessible")
                except Exception as e:
                    print(f"❌ {table} table issue: {e}")
                    return False
            
            # Test if quiz_user_uuid column exists in students
            try:
                if 'postgresql' in db_url:
                    result = conn.execute(text("""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name='students' 
                        AND column_name='quiz_user_uuid'
                    """))
                else:
                    result = conn.execute(text("PRAGMA table_info(students)"))
                    columns = [row[1] for row in result.fetchall()]
                    result = 'quiz_user_uuid' in columns
                
                if result:
                    print("✅ quiz_user_uuid column exists in students table")
                else:
                    print("❌ quiz_user_uuid column missing from students table")
                    return False
                    
            except Exception as e:
                print(f"❌ Error checking quiz_user_uuid column: {e}")
                return False
            
            print("✅ All migration tests passed!")
            return True
            
    except Exception as e:
        print(f"❌ Migration test failed: {e}")
        return False

def main():
    """Main migration function"""
    if run_quiz_migration():
        if test_migration():
            print("\n🚀 Ready to start your SkillsTown app!")
            print("Run: python app.py")
        else:
            print("\n⚠️  Migration completed but tests failed")
    else:
        print("\n❌ Migration failed. Please check the errors above.")
        sys.exit(1)

if __name__ == '__main__':
    main()