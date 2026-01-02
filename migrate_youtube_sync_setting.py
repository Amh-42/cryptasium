import sqlite3
import os

def migrate():
    db_path = os.path.join('instance', 'cryptasium.db')
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Add enable_youtube_sync column to user_settings table
        print("Adding enable_youtube_sync column to user_settings table...")
        cursor.execute("ALTER TABLE user_settings ADD COLUMN enable_youtube_sync BOOLEAN DEFAULT 0")
        conn.commit()
        print("Migration successful: Added enable_youtube_sync column.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("Migration skipped: Column enable_youtube_sync already exists.")
        else:
            print(f"Migration failed: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
