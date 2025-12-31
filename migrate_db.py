"""
Database migration script for Cryptasium.
Adds new columns and tables for the dynamic gamification system.
Run: python migrate_db.py
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models import db

def migrate():
    """Run database migrations"""
    print("\n=== Running Database Migrations ===\n")
    
    app = create_app()
    
    with app.app_context():
        # Get raw connection for executing ALTER TABLE
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        migrations = [
            # User table new columns
            ("ALTER TABLE users ADD COLUMN avatar_url VARCHAR(500)", "users.avatar_url"),
            ("ALTER TABLE users ADD COLUMN display_name VARCHAR(100)", "users.display_name"),
            ("ALTER TABLE users ADD COLUMN timezone VARCHAR(50) DEFAULT 'UTC'", "users.timezone"),
            
            # Content calendar user_id
            ("ALTER TABLE content_calendar_entries ADD COLUMN user_id INTEGER", "content_calendar_entries.user_id"),
            
            # TrackableType new columns for value tracking
            ("ALTER TABLE trackable_types ADD COLUMN xp_mode VARCHAR(20) DEFAULT 'fixed'", "trackable_types.xp_mode"),
            ("ALTER TABLE trackable_types ADD COLUMN xp_multiplier FLOAT DEFAULT 1.0", "trackable_types.xp_multiplier"),
            ("ALTER TABLE trackable_types ADD COLUMN tiers_config TEXT", "trackable_types.tiers_config"),
            ("ALTER TABLE trackable_types ADD COLUMN track_value BOOLEAN DEFAULT 0", "trackable_types.track_value"),
            ("ALTER TABLE trackable_types ADD COLUMN value_label VARCHAR(50) DEFAULT 'Value'", "trackable_types.value_label"),
            ("ALTER TABLE trackable_types ADD COLUMN value_prefix VARCHAR(10) DEFAULT '$'", "trackable_types.value_prefix"),
            ("ALTER TABLE trackable_types ADD COLUMN value_suffix VARCHAR(10) DEFAULT ''", "trackable_types.value_suffix"),
            ("ALTER TABLE trackable_types ADD COLUMN allows_negative BOOLEAN DEFAULT 0", "trackable_types.allows_negative"),
            ("ALTER TABLE trackable_types ADD COLUMN value_goal FLOAT DEFAULT 0", "trackable_types.value_goal"),
            
            # TrackableEntry new columns
            ("ALTER TABLE trackable_entries ADD COLUMN value FLOAT DEFAULT 0", "trackable_entries.value"),
            ("ALTER TABLE trackable_entries ADD COLUMN tier_name VARCHAR(50)", "trackable_entries.tier_name"),
            
            # UserSettings new columns
            ("ALTER TABLE user_settings ADD COLUMN accent_color VARCHAR(20) DEFAULT '#e90e0e'", "user_settings.accent_color"),
            
            # UserDailyTask new columns for flexible scheduling and count tasks
            ("ALTER TABLE user_daily_tasks ADD COLUMN task_type VARCHAR(20) DEFAULT 'normal'", "user_daily_tasks.task_type"),
            ("ALTER TABLE user_daily_tasks ADD COLUMN target_count INTEGER DEFAULT 1", "user_daily_tasks.target_count"),
            ("ALTER TABLE user_daily_tasks ADD COLUMN repeat_type VARCHAR(20) DEFAULT 'daily'", "user_daily_tasks.repeat_type"),
            ("ALTER TABLE user_daily_tasks ADD COLUMN repeat_interval INTEGER DEFAULT 1", "user_daily_tasks.repeat_interval"),
            ("ALTER TABLE user_daily_tasks ADD COLUMN repeat_days VARCHAR(50)", "user_daily_tasks.repeat_days"),
            ("ALTER TABLE user_daily_tasks ADD COLUMN repeat_day_of_month INTEGER", "user_daily_tasks.repeat_day_of_month"),
            ("ALTER TABLE user_daily_tasks ADD COLUMN due_date DATE", "user_daily_tasks.due_date"),
            ("ALTER TABLE user_daily_tasks ADD COLUMN completed_date DATE", "user_daily_tasks.completed_date"),
            ("ALTER TABLE user_daily_tasks ADD COLUMN ebbinghaus_level INTEGER DEFAULT 0", "user_daily_tasks.ebbinghaus_level"),
            ("ALTER TABLE user_daily_tasks ADD COLUMN next_due_date DATE", "user_daily_tasks.next_due_date"),
            ("ALTER TABLE user_daily_tasks ADD COLUMN xp_per_count INTEGER DEFAULT 0", "user_daily_tasks.xp_per_count"),
            ("ALTER TABLE user_daily_tasks ADD COLUMN streak_bonus BOOLEAN DEFAULT 1", "user_daily_tasks.streak_bonus"),
            ("ALTER TABLE user_daily_tasks ADD COLUMN emoji VARCHAR(10)", "user_daily_tasks.emoji"),
            ("ALTER TABLE user_daily_tasks ADD COLUMN is_pinned BOOLEAN DEFAULT 0", "user_daily_tasks.is_pinned"),
            ("ALTER TABLE user_daily_tasks ADD COLUMN category VARCHAR(50) DEFAULT 'general'", "user_daily_tasks.category"),
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
                    print(f"[SKIP] {description}: {str(e)[:50]}")
        
        # Create new tables if they don't exist
        print("\n[INFO] Creating new tables if they don't exist...")
        db.create_all()
        print("[OK] All tables created/verified")
        
        cursor.close()
        connection.close()
        
        print("\n=== Migration Complete ===\n")

if __name__ == '__main__':
    migrate()
