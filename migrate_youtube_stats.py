"""
Migration script to add YouTube sync columns to the users table.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models import db

def migrate():
    print("\n=== Running YouTube Sync Migrations ===\n")
    
    app = create_app()
    
    with app.app_context():
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        migrations = [
            ("ALTER TABLE users ADD COLUMN youtube_subscribers INTEGER DEFAULT 0", "users.youtube_subscribers"),
            ("ALTER TABLE users ADD COLUMN youtube_channel_views INTEGER DEFAULT 0", "users.youtube_channel_views"),
            ("ALTER TABLE users ADD COLUMN last_youtube_sync DATETIME", "users.last_youtube_sync"),
        ]
        
        for sql, description in migrations:
            try:
                cursor.execute(sql)
                connection.commit()
                print(f"[OK] Added {description}")
            except Exception as e:
                if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                    print(f"[SKIP] {description} already exists")
                else:
                    print(f"[ERROR] {description}: {str(e)}")
        
        # Ensure any other missing tables/columns from model are created
        db.create_all()
        
        cursor.close()
        connection.close()
        
        print("\n=== Migration Complete ===\n")

if __name__ == '__main__':
    migrate()
