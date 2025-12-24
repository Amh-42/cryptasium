"""
Database migration script to add gamification columns
Run this script once to update your existing database
"""
import sqlite3
import os

# Path to database
DB_PATH = os.path.join(os.path.dirname(__file__), 'instance', 'cryptasium.db')

def migrate():
    print(f"Migrating database at: {DB_PATH}")
    
    if not os.path.exists(DB_PATH):
        print("Database not found. It will be created when you run the app.")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    migrations = [
        # Add duration_seconds to youtube_videos
        ("youtube_videos", "duration_seconds", "INTEGER DEFAULT 0"),
        # Add content_type to youtube_videos  
        ("youtube_videos", "content_type", "VARCHAR(20) DEFAULT 'longs'"),
        # Add subscriber_points to gamification_stats
        ("gamification_stats", "subscriber_points", "INTEGER DEFAULT 0"),
        # Add views_points to gamification_stats
        ("gamification_stats", "views_points", "INTEGER DEFAULT 0"),
        # Add daily_xp_points to gamification_stats
        ("gamification_stats", "daily_xp_points", "INTEGER DEFAULT 0"),
        # Add likes to blog_posts
        ("blog_posts", "likes", "INTEGER DEFAULT 0"),
        # Add likes to youtube_videos
        ("youtube_videos", "likes", "INTEGER DEFAULT 0"),
        # Add likes to shorts
        ("shorts", "likes", "INTEGER DEFAULT 0"),
        # Add likes to podcasts
        ("podcasts", "likes", "INTEGER DEFAULT 0"),
    ]
    
    for table, column, column_type in migrations:
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")
            print(f"[OK] Added column '{column}' to '{table}'")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print(f"[--] Column '{column}' already exists in '{table}'")
            else:
                print(f"[ERROR] Error adding '{column}' to '{table}': {e}")
    
    # Create gamification_stats table if it doesn't exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gamification_stats (
            id INTEGER PRIMARY KEY,
            subscriber_count INTEGER DEFAULT 0,
            total_channel_views INTEGER DEFAULT 0,
            total_points INTEGER DEFAULT 0,
            total_content_count INTEGER DEFAULT 0,
            total_views INTEGER DEFAULT 0,
            current_rank_code VARCHAR(10) DEFAULT 'UNRANKED',
            current_rank_name VARCHAR(50) DEFAULT 'Unranked',
            blog_count INTEGER DEFAULT 0,
            shorts_count INTEGER DEFAULT 0,
            short_longs_count INTEGER DEFAULT 0,
            podcast_count INTEGER DEFAULT 0,
            mid_longs_count INTEGER DEFAULT 0,
            longs_count INTEGER DEFAULT 0,
            blog_points INTEGER DEFAULT 0,
            shorts_points INTEGER DEFAULT 0,
            short_longs_points INTEGER DEFAULT 0,
            podcast_points INTEGER DEFAULT 0,
            mid_longs_points INTEGER DEFAULT 0,
            longs_points INTEGER DEFAULT 0,
            subscriber_points INTEGER DEFAULT 0,
            views_points INTEGER DEFAULT 0,
            daily_xp_points INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_sync_at DATETIME
        )
    """)
    print("[OK] Created/verified 'gamification_stats' table")
    
    # Create content_calendar_entries table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS content_calendar_entries (
            id INTEGER PRIMARY KEY,
            scheduled_date DATE NOT NULL,
            scheduled_time TIME,
            content_type VARCHAR(50) NOT NULL,
            title VARCHAR(300) NOT NULL,
            description TEXT,
            status VARCHAR(20) DEFAULT 'planned',
            is_recurring BOOLEAN DEFAULT 0,
            recurring_day INTEGER,
            color VARCHAR(20) DEFAULT '#0ea5e9',
            linked_content_id INTEGER,
            linked_content_type VARCHAR(50),
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            completed_at DATETIME
        )
    """)
    print("[OK] Created/verified 'content_calendar_entries' table")
    
    # Create weekly_posting_schedule table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS weekly_posting_schedule (
            id INTEGER PRIMARY KEY,
            content_type VARCHAR(50) UNIQUE NOT NULL,
            content_label VARCHAR(100) NOT NULL,
            day_of_week INTEGER NOT NULL,
            preferred_time TIME,
            color VARCHAR(20) DEFAULT '#0ea5e9',
            icon VARCHAR(50) DEFAULT 'ph-calendar',
            is_active BOOLEAN DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("[OK] Created/verified 'weekly_posting_schedule' table")
    
    # Create weekly_content_plans table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS weekly_content_plans (
            id INTEGER PRIMARY KEY,
            week_start DATE NOT NULL,
            content_type VARCHAR(50) NOT NULL,
            title VARCHAR(300) NOT NULL,
            notes TEXT,
            status VARCHAR(20) DEFAULT 'planned',
            calendar_entry_id INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (calendar_entry_id) REFERENCES content_calendar_entries(id)
        )
    """)
    print("[OK] Created/verified 'weekly_content_plans' table")
    
    # Create index on week_start for faster lookups
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_weekly_plans_week ON weekly_content_plans(week_start)")
        print("[OK] Created index on 'weekly_content_plans.week_start'")
    except Exception as e:
        print(f"[--] Index may already exist: {e}")
    
    conn.commit()
    conn.close()
    
    print("\n=== Migration complete! ===")

if __name__ == "__main__":
    migrate()

