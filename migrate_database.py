#!/usr/bin/env python3
"""
Complete database migration script for SkillsTown application
This script will recreate all tables with the new schema
"""

import os
import sys
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import SQLAlchemyError

def get_database_url():
    """Get database URL from environment or use default"""
    db_url = os.environ.get('DATABASE_URL')
    if db_url and db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql://')
    return db_url or 'sqlite:///skillstown.db'

def drop_all_skillstown_tables():
    """Drop all existing SkillsTown tables"""
    db_url = get_database_url()
    engine = create_engine(db_url)
    
    try:
        with engine.connect() as conn:
            print("Dropping existing tables...")
            
            # Drop tables in correct order (respecting foreign key constraints)
            tables_to_drop = [
                'courses_content_pages',
                'skillstown_user_profiles', 
                'courses',
                'content_pages',
                'students',
                'companies',
                'category',
                'skillstown_courses',
                'skillstown_user_courses'  # Legacy table
            ]
            
            for table in tables_to_drop:
                try:
                    conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
                    print(f"✓ Dropped table: {table}")
                except SQLAlchemyError as e:
                    print(f"Note: Could not drop {table}: {e}")
            
            conn.commit()
            print("✓ All tables dropped successfully")
            
    except SQLAlchemyError as e:
        print(f"✗ Error dropping tables: {e}")
        return False
    
    return True

def create_new_schema():
    """Create the new database schema"""
    # Add the project directory to Python path
    project_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, project_dir)
    
    try:
        from app import create_app, db
        
        app = create_app()
        
        with app.app_context():
            print("Creating new database schema...")
            
            # Create all tables
            db.create_all()
            
            print("✓ New schema created successfully")
            
            # Insert sample data
            insert_sample_data(db)
            
    except Exception as e:
        print(f"✗ Error creating schema: {e}")
        return False
    
    return True

def insert_sample_data(db):
    """Insert sample data for testing"""
    from models import Company, Category, Student, ContentPage, SkillsTownCourse
    
    try:
        print("Inserting sample data...")
        
        # Create sample companies
        companies = [
            Company(name="TechCorp Inc", industry="Technology"),
            Company(name="DataSystems Ltd", industry="Data Analytics"),
            Company(name="CloudWorks", industry="Cloud Computing")
        ]
        
        for company in companies:
            db.session.add(company)
        
        # Create categories
        categories = [
            Category(name="Programming Languages"),
            Category(name="Web Development"), 
            Category(name="Data Science & Analytics"),
            Category(name="Cloud Computing"),
            Category(name="DevOps & Tools"),
            Category(name="Mobile Development"),
            Category(name="Cybersecurity"),
            Category(name="Artificial Intelligence")
        ]
        
        for category in categories:
            db.session.add(category)
        
        db.session.commit()
        
        # Create sample content pages
        programming_category = Category.query.filter_by(name="Programming Languages").first()
        web_category = Category.query.filter_by(name="Web Development").first()
        data_category = Category.query.filter_by(name="Data Science & Analytics").first()
        
        content_pages = [
            ContentPage(
                category_id=programming_category.id,
                title="Python Basics",
                content='{"type": "lesson", "duration": "2 hours", "topics": ["Variables", "Data Types", "Control Flow"]}',
                is_draft=False
            ),
            ContentPage(
                category_id=programming_category.id,
                title="Advanced Python",
                content='{"type": "lesson", "duration": "3 hours", "topics": ["OOP", "Decorators", "Async Programming"]}',
                is_draft=False
            ),
            ContentPage(
                category_id=web_category.id,
                title="React Fundamentals",
                content='{"type": "lesson", "duration": "4 hours", "topics": ["Components", "State", "Props", "Hooks"]}',
                is_draft=False
            ),
            ContentPage(
                category_id=data_category.id,
                title="Machine Learning Intro",
                content='{"type": "lesson", "duration": "5 hours", "topics": ["Supervised Learning", "Unsupervised Learning", "Model Evaluation"]}',
                is_draft=False
            )
        ]
        
        for page in content_pages:
            db.session.add(page)
        
        # Create sample courses from existing course catalog
        sample_courses = [
            SkillsTownCourse(
                category="Programming Languages",
                name="Python for Beginners",
                description="Learn Python programming from scratch with hands-on projects and real-world applications.",
                skills_taught="Python, Programming Fundamentals, Problem Solving",
                difficulty_level="Beginner",
                duration="8 weeks"
            ),
            SkillsTownCourse(
                category="Web Development", 
                name="React Complete Course",
                description="Build modern web applications with React, including hooks, context, and state management.",
                skills_taught="React, JavaScript, HTML, CSS, Frontend Development",
                difficulty_level="Intermediate",
                duration="10 weeks"
            ),
            SkillsTownCourse(
                category="Data Science & Analytics",
                name="Machine Learning Fundamentals", 
                description="Understand machine learning algorithms and implement them using scikit-learn and TensorFlow.",
                skills_taught="Machine Learning, Python, Data Analysis, Statistics",
                difficulty_level="Intermediate",
                duration="12 weeks"
            ),
            SkillsTownCourse(
                category="Cloud Computing",
                name="AWS Cloud Practitioner",
                description="Learn Amazon Web Services fundamentals and cloud computing concepts.",
                skills_taught="AWS, Cloud Computing, Infrastructure, DevOps",
                difficulty_level="Beginner",
                duration="6 weeks"
            )
        ]
        
        for course in sample_courses:
            db.session.add(course)
        
        db.session.commit()
        print("✓ Sample data inserted successfully")
        
    except Exception as e:
        print(f"✗ Error inserting sample data: {e}")
        db.session.rollback()

def verify_schema():
    """Verify that the new schema was created correctly"""
    db_url = get_database_url()
    engine = create_engine(db_url)
    
    try:
        with engine.connect() as conn:
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            
            expected_tables = [
                'companies',
                'students', 
                'category',
                'content_pages',
                'courses',
                'courses_content_pages',
                'skillstown_user_profiles',
                'skillstown_courses'
            ]
            
            print("\nVerifying schema...")
            all_good = True
            
            for table in expected_tables:
                if table in tables:
                    print(f"✓ {table} table exists")
                    
                    # Check some key columns
                    columns = [col['name'] for col in inspector.get_columns(table)]
                    print(f"  Columns: {', '.join(columns)}")
                else:
                    print(f"✗ {table} table missing")
                    all_good = False
            
            # Check foreign key relationships
            print("\nChecking foreign key relationships...")
            
            # Students -> Companies
            students_fks = inspector.get_foreign_keys('students')
            company_fk_exists = any(fk['referred_table'] == 'companies' for fk in students_fks)
            print(f"✓ Students->Companies FK: {'Yes' if company_fk_exists else 'No'}")
            
            # Courses -> Students and Categories
            courses_fks = inspector.get_foreign_keys('courses')
            student_fk_exists = any(fk['referred_table'] == 'students' for fk in courses_fks)
            category_fk_exists = any(fk['referred_table'] == 'category' for fk in courses_fks)
            print(f"✓ Courses->Students FK: {'Yes' if student_fk_exists else 'No'}")
            print(f"✓ Courses->Categories FK: {'Yes' if category_fk_exists else 'No'}")
            
            # Content Pages -> Categories
            content_fks = inspector.get_foreign_keys('content_pages')
            content_category_fk_exists = any(fk['referred_table'] == 'category' for fk in content_fks)
            print(f"✓ ContentPages->Categories FK: {'Yes' if content_category_fk_exists else 'No'}")
            
            if all_good:
                print("\n🎉 Schema verification completed successfully!")
                return True
            else:
                print("\n⚠️  Schema verification found issues.")
                return False
                
    except SQLAlchemyError as e:
        print(f"✗ Verification error: {e}")
        return False
                
def migrate_database():
    """Add missing columns to existing tables and create course details table"""
    try:
        # Perform standard migrations (if any)
        # Add new course details table
        # Use application context database object
        from app import create_app, db
        app = create_app()
        with app.app_context():
            db.create_all()
            print("✓ Course details table created")
        # Add any other migration steps for job_description or skill_analysis columns here
    except Exception as e:
        print(f"Migration note: {e}")
        try:
            from app import db
            db.session.rollback()
        except:
            pass

def main():
    """Main migration function"""
    print("SkillsTown Database Migration Tool")
    print("=" * 40)
    print("WARNING: This will drop and recreate all SkillsTown tables!")
    
    confirm = input("Are you sure you want to continue? (yes/no): ")
    if confirm.lower() != 'yes':
        print("Migration cancelled.")
        return
    
    # Step 1: Drop existing tables
    if not drop_all_skillstown_tables():
        print("❌ Failed to drop existing tables")
        sys.exit(1)
    
    # Step 2: Create new schema  
    if not create_new_schema():
        print("❌ Failed to create new schema")
        sys.exit(1)
    
    # Step 3: Verify everything worked
    if verify_schema():
        print("\n🎉 Migration completed successfully!")
        print("Your SkillsTown application is ready to use with the new schema.")
    else:
        print("\n⚠️  Migration completed but verification failed.")
        print("Please check the database manually.")

if __name__ == '__main__':
    main()