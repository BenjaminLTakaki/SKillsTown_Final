# Manual migration script for UserLearningProgress table
# Run this script once to create the table

import sqlite3
import os

def create_user_learning_progress_table():
    """Create the UserLearningProgress table in SQLite database"""
    
    # Database file path (adjust if your database is in a different location)
    db_path = 'instance/skillstown_dev.db'  # or 'skillstown.db' depending on your setup
    
    # Check if database exists
    if not os.path.exists(db_path):
        print(f"Database file {db_path} not found. Please check the path.")
        return False
    
    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if table already exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='skillstown_user_learning_progress'
        """)
        
        if cursor.fetchone():
            print("Table 'skillstown_user_learning_progress' already exists.")
            conn.close()
            return True
        
        # Create the UserLearningProgress table
        cursor.execute("""
            CREATE TABLE skillstown_user_learning_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id VARCHAR(36) NOT NULL,
                course_id VARCHAR(50) NOT NULL,
                knowledge_areas TEXT DEFAULT '{}',
                weak_areas TEXT DEFAULT '[]',
                strong_areas TEXT DEFAULT '[]',
                recommended_topics TEXT DEFAULT '[]',
                learning_curve TEXT DEFAULT '[]',
                overall_progress INTEGER DEFAULT 0,
                mastery_level VARCHAR(20) DEFAULT 'beginner',
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES students (id),
                UNIQUE (user_id, course_id)
            )
        """)
        
        # Create index for faster queries
        cursor.execute("""
            CREATE INDEX idx_user_course_progress 
            ON skillstown_user_learning_progress (user_id, course_id)
        """)
        
        # Commit the changes
        conn.commit()
        conn.close()
        
        print("✅ Successfully created 'skillstown_user_learning_progress' table!")
        return True
        
    except sqlite3.Error as e:
        print(f"❌ Error creating table: {e}")
        return False

if __name__ == "__main__":
    print("🔄 Creating UserLearningProgress table...")
    success = create_user_learning_progress_table()
    
    if success:
        print("✅ Migration completed successfully!")
        print("You can now use the learning progress features.")
    else:
        print("❌ Migration failed. Please check the error messages above.")