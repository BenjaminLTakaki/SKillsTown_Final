import os
import sys
from sqlalchemy import create_engine, text, inspect

def get_database_url():
    """Get database URL from environment"""
    db_url = os.environ.get('DATABASE_URL')
    if db_url and db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql://')
    return db_url or 'sqlite:///skillstown.db'

def create_all_tables():
    """Create all tables from scratch"""
    
    print("🔧 Creating ALL SkillsTown tables...")
    
    db_url = get_database_url()
    engine = create_engine(db_url)
    
    print(f"Database: {db_url}")
    
    try:
        with engine.connect() as conn:
            trans = conn.begin()
            
            try:
                is_postgresql = 'postgresql' in db_url
                
                # 1. Create companies table
                print("📝 Creating companies table...")
                if is_postgresql:
                    conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS companies (
                            id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
                            name VARCHAR(255) NOT NULL,
                            industry VARCHAR(255),
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """))
                else:
                    conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS companies (
                            id VARCHAR(36) PRIMARY KEY,
                            name VARCHAR(255) NOT NULL,
                            industry VARCHAR(255),
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """))
                print("✅ companies table created")
                
                # 2. Create students table
                print("📝 Creating students table...")
                if is_postgresql:
                    conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS students (
                            id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
                            name VARCHAR(255) NOT NULL,
                            email VARCHAR(255) NOT NULL UNIQUE,
                            enrolled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            company_id VARCHAR(36) REFERENCES companies(id),
                            username VARCHAR(255),
                            password_hash VARCHAR(255),
                            is_active BOOLEAN DEFAULT true,
                            date_joined TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            quiz_user_uuid VARCHAR(36) UNIQUE
                        )
                    """))
                else:
                    conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS students (
                            id VARCHAR(36) PRIMARY KEY,
                            name VARCHAR(255) NOT NULL,
                            email VARCHAR(255) NOT NULL UNIQUE,
                            enrolled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            company_id VARCHAR(36),
                            username VARCHAR(255),
                            password_hash VARCHAR(255),
                            is_active BOOLEAN DEFAULT 1,
                            date_joined TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            quiz_user_uuid VARCHAR(36) UNIQUE,
                            FOREIGN KEY (company_id) REFERENCES companies(id)
                        )
                    """))
                print("✅ students table created")
                
                # 3. Create category table
                print("📝 Creating category table...")
                if is_postgresql:
                    conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS category (
                            id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
                            name VARCHAR(255) NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """))
                else:
                    conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS category (
                            id VARCHAR(36) PRIMARY KEY,
                            name VARCHAR(255) NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """))
                print("✅ category table created")
                
                # 4. Create content_pages table
                print("📝 Creating content_pages table...")
                if is_postgresql:
                    conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS content_pages (
                            id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
                            category_id VARCHAR(36) NOT NULL REFERENCES category(id),
                            title VARCHAR(255) NOT NULL,
                            content TEXT,
                            is_draft BOOLEAN DEFAULT false,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """))
                else:
                    conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS content_pages (
                            id VARCHAR(36) PRIMARY KEY,
                            category_id VARCHAR(36) NOT NULL,
                            title VARCHAR(255) NOT NULL,
                            content TEXT,
                            is_draft BOOLEAN DEFAULT 0,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (category_id) REFERENCES category(id)
                        )
                    """))
                print("✅ content_pages table created")
                
                # 5. Create courses table
                print("📝 Creating courses table...")
                if is_postgresql:
                    conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS courses (
                            id VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
                            student_id VARCHAR(36) NOT NULL REFERENCES students(id),
                            name VARCHAR(255) NOT NULL,
                            description TEXT,
                            category_id VARCHAR(36) NOT NULL REFERENCES category(id),
                            published BOOLEAN DEFAULT false,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            status VARCHAR(50) DEFAULT 'enrolled',
                            progress_percentage INTEGER DEFAULT 0,
                            completed_at TIMESTAMP
                        )
                    """))
                else:
                    conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS courses (
                            id VARCHAR(36) PRIMARY KEY,
                            student_id VARCHAR(36) NOT NULL,
                            name VARCHAR(255) NOT NULL,
                            description TEXT,
                            category_id VARCHAR(36) NOT NULL,
                            published BOOLEAN DEFAULT 0,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            status VARCHAR(50) DEFAULT 'enrolled',
                            progress_percentage INTEGER DEFAULT 0,
                            completed_at TIMESTAMP,
                            FOREIGN KEY (student_id) REFERENCES students(id),
                            FOREIGN KEY (category_id) REFERENCES category(id)
                        )
                    """))
                print("✅ courses table created")
                
                # 6. Create courses_content_pages table
                print("📝 Creating courses_content_pages table...")
                if is_postgresql:
                    conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS courses_content_pages (
                            course_id VARCHAR(36) NOT NULL REFERENCES courses(id),
                            content_page_id VARCHAR(36) NOT NULL REFERENCES content_pages(id),
                            order_index INTEGER NOT NULL,
                            is_required BOOLEAN DEFAULT true,
                            PRIMARY KEY (course_id, content_page_id)
                        )
                    """))
                else:
                    conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS courses_content_pages (
                            course_id VARCHAR(36) NOT NULL,
                            content_page_id VARCHAR(36) NOT NULL,
                            order_index INTEGER NOT NULL,
                            is_required BOOLEAN DEFAULT 1,
                            PRIMARY KEY (course_id, content_page_id),
                            FOREIGN KEY (course_id) REFERENCES courses(id),
                            FOREIGN KEY (content_page_id) REFERENCES content_pages(id)
                        )
                    """))
                print("✅ courses_content_pages table created")
                
                # 7. Create skillstown_user_profiles table
                print("📝 Creating skillstown_user_profiles table...")
                if is_postgresql:
                    conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS skillstown_user_profiles (
                            id SERIAL PRIMARY KEY,
                            user_id VARCHAR(36) NOT NULL REFERENCES students(id),
                            cv_text TEXT,
                            job_description TEXT,
                            skills TEXT,
                            skill_analysis TEXT,
                            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """))
                else:
                    conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS skillstown_user_profiles (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id VARCHAR(36) NOT NULL,
                            cv_text TEXT,
                            job_description TEXT,
                            skills TEXT,
                            skill_analysis TEXT,
                            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (user_id) REFERENCES students(id)
                        )
                    """))
                print("✅ skillstown_user_profiles table created")
                
                # 8. Create skillstown_courses table
                print("📝 Creating skillstown_courses table...")
                if is_postgresql:
                    conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS skillstown_courses (
                            id SERIAL PRIMARY KEY,
                            category VARCHAR(100) NOT NULL,
                            name VARCHAR(255) NOT NULL,
                            description TEXT,
                            url VARCHAR(500),
                            provider VARCHAR(100) DEFAULT 'SkillsTown',
                            skills_taught TEXT,
                            difficulty_level VARCHAR(20),
                            duration VARCHAR(50),
                            keywords TEXT,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """))
                else:
                    conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS skillstown_courses (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            category VARCHAR(100) NOT NULL,
                            name VARCHAR(255) NOT NULL,
                            description TEXT,
                            url VARCHAR(500),
                            provider VARCHAR(100) DEFAULT 'SkillsTown',
                            skills_taught TEXT,
                            difficulty_level VARCHAR(20),
                            duration VARCHAR(50),
                            keywords TEXT,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """))
                print("✅ skillstown_courses table created")
                
                # 9. Create skillstown_user_courses table
                print("📝 Creating skillstown_user_courses table...")
                if is_postgresql:
                    conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS skillstown_user_courses (
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
                        CREATE TABLE IF NOT EXISTS skillstown_user_courses (
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
                
                # 10. Create skillstown_course_details table
                print("📝 Creating skillstown_course_details table...")
                if is_postgresql:
                    conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS skillstown_course_details (
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
                        CREATE TABLE IF NOT EXISTS skillstown_course_details (
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
                
                # 11. Create skillstown_course_quizzes table
                print("📝 Creating skillstown_course_quizzes table...")
                if is_postgresql:
                    conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS skillstown_course_quizzes (
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
                print("✅ skillstown_course_quizzes table created")
                
                # 12. Create skillstown_quiz_attempts table
                print("📝 Creating skillstown_quiz_attempts table...")
                if is_postgresql:
                    conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS skillstown_quiz_attempts (
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
                print("✅ skillstown_quiz_attempts table created")
                
                # Commit all changes
                trans.commit()
                print("\n🎉 All database tables created successfully!")
                
                return True
                
            except Exception as e:
                trans.rollback()
                print(f"❌ Error creating tables: {e}")
                import traceback
                traceback.print_exc()
                return False
                
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

def test_all_tables():
    """Test if all tables were created correctly"""
    print("\n🔍 Testing all table creation...")
    
    db_url = get_database_url()
    engine = create_engine(db_url)
    
    required_tables = [
        'companies',
        'students',
        'category',
        'content_pages',
        'courses',
        'courses_content_pages',
        'skillstown_user_profiles',
        'skillstown_courses',
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

def create_sample_user():
    """Create a sample user for testing"""
    print("\n👤 Creating sample user...")
    
    try:
        # Import app to create user
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        
        # Create Flask app context
        from app import create_app
        app = create_app()
        
        with app.app_context():
            from models import db, Student
            from werkzeug.security import generate_password_hash
            import uuid
            
            # Check if user already exists
            existing_user = Student.query.filter_by(email='test@skillstown.com').first()
            if existing_user:
                print("✅ Sample user already exists: test@skillstown.com")
                return True
            
            # Create sample user
            user = Student(
                id=str(uuid.uuid4()),
                name='Test User',
                email='test@skillstown.com',
                username='testuser',
                password_hash=generate_password_hash('password123'),
                is_active=True
            )
            
            db.session.add(user)
            db.session.commit()
            
            print("✅ Sample user created:")
            print("   Email: test@skillstown.com")
            print("   Password: password123")
            return True
            
    except Exception as e:
        print(f"❌ Error creating sample user: {e}")
        return False

def create_sample_courses():
    """Create sample courses for testing"""
    print("\n📚 Creating sample courses...")
    
    try:
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from app import create_app
        
        app = create_app()
        with app.app_context():
            from models import db, Student
            
            # Get the test user
            user = Student.query.filter_by(email='test@skillstown.com').first()
            if not user:
                print("❌ No test user found. Run create_sample_user first.")
                return False
            
            # Import UserCourse model from app
            from app import UserCourse
            
            # Check if courses already exist
            existing_courses = UserCourse.query.filter_by(user_id=user.id).count()
            if existing_courses > 0:
                print(f"✅ User already has {existing_courses} courses")
                return True
            
            # Create sample courses
            sample_courses = [
                {"category": "Programming Languages", "course_name": "Python for Beginners"},
                {"category": "Web Development", "course_name": "React Complete Course"},
                {"category": "Data Science & Analytics", "course_name": "Data Science with Python"},
                {"category": "Cloud Computing", "course_name": "AWS Cloud Practitioner"}
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
            print(f"✅ Created {len(sample_courses)} sample courses")
            return True
            
    except Exception as e:
        print(f"❌ Error creating sample courses: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main function"""
    print("🎯 Complete SkillsTown Database Setup")
    print("=" * 50)
    
    # Create all tables
    if not create_all_tables():
        print("\n❌ Database setup failed!")
        sys.exit(1)
    
    # Test all tables
    if not test_all_tables():
        print("\n❌ Table verification failed!")
        sys.exit(1)
    
    # Create sample user
    if not create_sample_user():
        print("\n⚠️  Could not create sample user, but database setup is complete")
    
    # Create sample courses
    if not create_sample_courses():
        print("\n⚠️  Could not create sample courses, but database setup is complete")
    
    print("\n🚀 Complete database setup finished!")
    print("\nNext steps:")
    print("1. Start your app: python app.py")
    print("2. Login with: test@skillstown.com / password123")
    print("3. Go to 'My Courses' and try generating a quiz!")
    print("\nOr register a new account and upload your CV for analysis.")

if __name__ == '__main__':
    main()