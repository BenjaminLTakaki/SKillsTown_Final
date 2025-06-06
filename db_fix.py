#!/usr/bin/env python3
"""
Aggressive fix - drops ALL SkillsTown tables
"""

import os
from sqlalchemy import create_engine, text

def aggressive_fix():
    """Drop ALL SkillsTown related tables"""
    
    db_url = os.environ.get('DATABASE_URL')
    if db_url and db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql://')
    
    if not db_url:
        print("❌ No DATABASE_URL found")
        return False
    
    engine = create_engine(db_url)
    
    try:
        with engine.connect() as conn:
            print("🔧 AGGRESSIVE FIX: Dropping all SkillsTown tables...")
            
            # Kill any active connections and rollback
            try:
                conn.execute(text("ROLLBACK"))
            except:
                pass
            
            # Drop ALL SkillsTown tables
            all_tables = [
                'skillstown_course_details',
                'skillstown_user_courses', 
                'skillstown_user_profiles',
                'skillstown_courses',
                'courses_content_pages',
                'courses',
                'content_pages',
                'students',
                'companies', 
                'category'
            ]
            
            for table in all_tables:
                try:
                    conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
                    print(f"✅ Dropped {table}")
                except Exception as e:
                    print(f"⚠️  Could not drop {table}: {e}")
            
            conn.commit()
            print("✅ ALL tables dropped!")
            return True
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == '__main__':
    print("⚠️  WARNING: This will drop ALL your SkillsTown data!")
    if aggressive_fix():
        print("\n🎉 Aggressive fix complete! Now run: python manage.py db upgrade && gunicorn wsgi:application")
    else:
        print("\n❌ Fix failed.")