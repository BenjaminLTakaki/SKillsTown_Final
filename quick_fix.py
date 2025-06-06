import os
import sys
from sqlalchemy import create_engine, text, inspect

def get_database_url():
    """Get database URL from environment"""
    db_url = os.environ.get('DATABASE_URL')
    if db_url and db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql://')
    return db_url or 'sqlite:///skillstown.db'

def create_missing_tables():
    """Create all missing tables for quiz integration"""
    
    print("🔧 Creating missing tables for quiz integration...")
    
    db_url = get_database_url()
    engine = create_engine(db_url)
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    
    print(f"Database: {db_url}")
    print(f"Existing tables: {existing_tables}")
    
    try:
        with engine.connect() as conn:
            trans = conn.begin()
            
            try:
                # 1. Create skillstown_user_courses table if not exists
                if 'skillstown_user_courses' not in existing_tables:
                    print("📝 Creating skillstown_user_courses table...")
                    
                    if 'postgresql' in db_url:
                        conn.execute(text("""
                            CREATE TABLE skillstown_user_courses (
                                id SERIAL PRIMARY KEY,
                                user_id VARCHAR(36) NOT NULL REFERENCES students(id) ON DELETE CASCADE,
                                category VARCHAR(100) NOT NULL,
                                course_name VARCHAR(255) NOT NULL,
                                status VARCHAR(50) DEFAULT 'enrolled',
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                CONSTRAINT skillstown_user_course_unique UNIQUE (user_id, course_name)
                            )
                        """))
                    else:
                        conn.execute(text("""
                            CREATE TABLE skillstown_user_courses (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                user_id VARCHAR(36) NOT NULL,
                                category VARCHAR(100) NOT NULL,
                                course_name VARCHAR(255) NOT NULL,
                                status VARCHAR(50) DEFAULT 'enrolled',
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                FOREIGN KEY (user_id) REFERENCES students(id) ON DELETE CASCADE,
                                UNIQUE (user_id, course_name)
                            )
                        """))
                    print("✅ skillstown_user_courses table created")
                else:
                    print("✅ skillstown_user_courses table already exists")
                
                # 2. Add quiz_user_uuid column to students if not exists
                print("📝 Checking quiz_user_uuid column in students table...")
                
                columns = [col['name'] for col in inspector.get_columns('students')]
                if 'quiz_user_uuid' not in columns:
                    if 'postgresql' in db_url:
                        conn.execute(text("ALTER TABLE students ADD COLUMN quiz_user_uuid VARCHAR(36) UNIQUE"))
                    else:
                        conn.execute(text("ALTER TABLE students ADD COLUMN quiz_user_uuid TEXT UNIQUE"))
                    print("✅ quiz_user_uuid column added to students")
                else:
                    print("✅ quiz_user_uuid column already exists")
                
                # 3. Create skillstown_course_details table if not exists
                if 'skillstown_course_details' not in existing_tables:
                    print("📝 Creating skillstown_course_details table...")
                    
                    if 'postgresql' in db_url:
                        conn.execute(text("""
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
                        """))
                    else:
                        conn.execute(text("""
                            CREATE TABLE skillstown_course_details (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                user_course_id INTEGER NOT NULL,
                                description TEXT,
                                progress_percentage INTEGER DEFAULT 0,
                                completed_at TIMESTAMP,
                                materials TEXT,
                                quiz_results TEXT,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                FOREIGN KEY (user_course_id) REFERENCES skillstown_user_courses(id) ON DELETE CASCADE
                            )
                        """))
                    print("✅ skillstown_course_details table created")
                else:
                    print("✅ skillstown_course_details table already exists")
                
                # 4. Create skillstown_course_quizzes table if not exists
                if 'skillstown_course_quizzes' not in existing_tables:
                    print("📝 Creating skillstown_course_quizzes table...")
                    
                    if 'postgresql' in db_url:
                        conn.execute(text("""
                            CREATE TABLE skillstown_course_quizzes (
                                id SERIAL PRIMARY KEY,
                                user_course_id INTEGER NOT NULL REFERENCES skillstown_user_courses(id) ON DELETE CASCADE,
                                quiz_api_id VARCHAR(100) NOT NULL,
                                quiz_title VARCHAR(255),
                                quiz_description TEXT,
                                questions_count INTEGER,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )
                        """))
                    else:
                        conn.execute(text("""
                            CREATE TABLE skillstown_course_quizzes (
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
                    print("✅ skillstown_course_quizzes table created")
                else:
                    print("✅ skillstown_course_quizzes table already exists")
                
                # 5. Create skillstown_quiz_attempts table if not exists
                if 'skillstown_quiz_attempts' not in existing_tables:
                    print("📝 Creating skillstown_quiz_attempts table...")
                    
                    if 'postgresql' in db_url:
                        conn.execute(text("""
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
                        """))
                    else:
                        conn.execute(text("""
                            CREATE TABLE skillstown_quiz_attempts (
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
                    print("✅ skillstown_quiz_attempts table created")
                else:
                    print("✅ skillstown_quiz_attempts table already exists")
                
                # Commit all changes
                trans.commit()
                print("\n🎉 All database tables created successfully!")
                
                return True
                
            except Exception as e:
                trans.rollback()
                print(f"❌ Error creating tables: {e}")
                return False
                
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

def test_tables():
    """Test if all tables were created correctly"""
    print("\n🔍 Testing table creation...")
    
    db_url = get_database_url()
    engine = create_engine(db_url)
    
    required_tables = [
        'students',
        'skillstown_user_courses', 
        'skillstown_course_details',
        'skillstown_course_quizzes',
        'skillstown_quiz_attempts'
    ]
    
    try:
        with engine.connect() as conn:
            for table in required_tables:
                try:
                    result = conn.execute(text(f"SELECT COUNT(*) FROM {table} LIMIT 1"))
                    print(f"✅ {table} - OK")
                except Exception as e:
                    print(f"❌ {table} - ERROR: {e}")
                    return False
            
            # Test quiz_user_uuid column
            try:
                inspector = inspect(engine)
                columns = [col['name'] for col in inspector.get_columns('students')]
                if 'quiz_user_uuid' in columns:
                    print("✅ students.quiz_user_uuid column - OK")
                else:
                    print("❌ students.quiz_user_uuid column - MISSING")
                    return False
            except Exception as e:
                print(f"❌ Error checking columns: {e}")
                return False
            
            print("✅ All tables and columns verified!")
            return True
            
    except Exception as e:
        print(f"❌ Table verification failed: {e}")
        return False

def create_sample_data():
    """Create sample course data for testing"""
    print("\n📊 Creating sample course data...")
    
    try:
        # Import app to get current user
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from app import create_app
        
        app = create_app()
        with app.app_context():
            from models import db, Student
            
            # Check if we have any users
            users = Student.query.all()
            if not users:
                print("⚠️  No users found. Please register a user first.")
                return True
            
            user = users[0]  # Use first user for sample data
            
            # Import UserCourse model
            from app import UserCourse
            
            # Check if user has courses
            existing_courses = UserCourse.query.filter_by(user_id=user.id).count()
            if existing_courses > 0:
                print(f"✅ User already has {existing_courses} courses")
                return True
            
            # Create sample courses
            sample_courses = [
                {"category": "Programming Languages", "course_name": "Python for Beginners"},
                {"category": "Web Development", "course_name": "React Complete Course"},
                {"category": "Data Science & Analytics", "course_name": "Data Science with Python"}
            ]
            
            for course_data in sample_courses:
                course = UserCourse(
                    user_id=user.id,
                    category=course_data["category"],
                    course_name=course_data["course_name"],
                    status='enrolled'
                )
                db.session.add(course)
            
            db.session.commit()
            print(f"✅ Created {len(sample_courses)} sample courses for user {user.username}")
            return True
            
    except Exception as e:
        print(f"❌ Error creating sample data: {e}")
        return False

def main():
    """Main function"""
    print("🎯 Quiz Integration Database Setup")
    print("=" * 50)
    
    # Create tables
    if not create_missing_tables():
        print("\n❌ Database setup failed!")
        sys.exit(1)
    
    # Test tables
    if not test_tables():
        print("\n❌ Table verification failed!")
        sys.exit(1)
    
    # Create sample data
    create_sample_data()
    
    print("\n🚀 Database setup complete!")
    print("\nNext steps:")
    print("1. Start your app: python app.py")
    print("2. Login to your account")
    print("3. Go to 'My Courses' and select a course")
    print("4. Try generating a quiz!")

if __name__ == '__main__':
    main()