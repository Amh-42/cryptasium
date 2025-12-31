import sqlite3
import os

DB_NAME = "instance/cryptasium.db"

def init_db():
    if not os.path.exists(DB_NAME):
        print(f"Database {DB_NAME} not found. Run the app once to create it.")
        return None

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    print("Creating dynamic tracking tables...")
    
    # Create user_metrics table
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            slug TEXT NOT NULL,
            metric_type TEXT DEFAULT 'manual',
            icon TEXT DEFAULT 'ph-star',
            color TEXT DEFAULT '#ffffff',
            description TEXT,
            xp_per_unit INTEGER DEFAULT 0,
            linked_content_type TEXT,
            current_value REAL DEFAULT 0,
            target_value REAL DEFAULT 0,
            display_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Create user_ranks table
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_ranks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            level INTEGER NOT NULL,
            name TEXT NOT NULL,
            min_xp INTEGER DEFAULT 0,
            icon TEXT,
            color TEXT DEFAULT '#666666',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Add index
    try:
        c.execute('CREATE INDEX IF NOT EXISTS idx_user_metrics_user_id ON user_metrics (user_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_user_ranks_user_id ON user_ranks (user_id)')
    except Exception as e:
        print(f"Index creation warning: {e}")

    conn.commit()
    return conn

def migrate_admin_data(conn):
    if not conn: return
    c = conn.cursor()
    
    # Get Admin User ID (assuming username='admin')
    c.execute("SELECT id FROM users WHERE username='admin'")
    admin_user = c.fetchone()
    if not admin_user:
        print("Admin user not found, checking for first user...")
        c.execute("SELECT id FROM users LIMIT 1")
        admin_user = c.fetchone()
        
    if not admin_user:
        print("No users found. Skipping data migration.")
        return
    
    admin_id = admin_user[0]
    print(f"Migrating defaults for User ID: {admin_id}...")
    
    # 1. Migrate Point Values -> UserMetrics
    
    # Define the standard metrics based on what was in models.py
    standard_metrics = [
        # (name, slug, type, icon, color, linked_type, xp, order)
        ('Daily XP', 'daily_xp_points', 'manual', 'ph-lightning', '#E90E0E', None, 1, 0),
        ('Blog Posts', 'blog', 'auto_count', 'ph-article', '#FFFFFF', 'blog_posts', 50, 1),
        ('Shorts', 'shorts', 'auto_count', 'ph-video', '#FFFFFF', 'shorts', 100, 2),
        ('Short Longs', 'short_longs', 'auto_count', 'ph-clock', '#FFFFFF', 'youtube_videos', 200, 3), # Requires logic in app.py
        ('Podcasts', 'podcast', 'auto_count', 'ph-microphone', '#FFFFFF', 'podcasts', 400, 4),
        ('Mid Longs', 'mid_longs', 'auto_count', 'ph-clock', '#FFFFFF', 'youtube_videos', 800, 5),
        ('Longs', 'longs', 'auto_count', 'ph-film-strip', '#FFFFFF', 'youtube_videos', 1000, 6),
        ('Subscribers', 'subscriber_count', 'manual', 'ph-users', '#0EA5E9', None, 20, 7),
        ('Views', 'views_points', 'manual', 'ph-eye', '#22C55E', None, 0.5, 8)
    ]
    
    # Check if metrics exist
    c.execute("SELECT count(*) FROM user_metrics WHERE user_id=?", (admin_id,))
    count = c.fetchone()[0]
    
    if count == 0:
        print(" seeding metrics...")
        for m in standard_metrics:
            name, slug, mtype, icon, color, link, xp, order = m
            c.execute('''
                INSERT INTO user_metrics 
                (user_id, name, slug, metric_type, icon, color, linked_content_type, xp_per_unit, display_order, current_value)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            ''', (admin_id, name, slug, mtype, icon, color, link, xp, order))
    else:
        print(" metrics already exist.")
        
    # 2. Migrate Ranks -> UserRanks
    c.execute("SELECT count(*) FROM user_ranks WHERE user_id=?", (admin_id,))
    count = c.fetchone()[0]
    
    if count == 0:
        print(" seeding ranks...")
        ranks = [
            (1, 'Beginner Token', 0, 'PNG/BT.png', '#8B4513'),
            (2, 'Habit Builder', 2500, 'PNG/HB.png', '#CD853F'),
            (3, 'Standing Out', 10000, 'PNG/SO.png', '#B8860B'),
            (4, 'Team Player', 50000, 'PNG/TP.png', '#4682B4'),
            (5, 'Flight Lead', 200000, 'PNG/FL.png', '#6A5ACD'),
            (6, 'Master Strategist', 500000, 'PNG/MS.png', '#FFD700'),
            (7, 'Empire Architect', 1000000, 'PNG/EA.png', '#9932CC'),
            (8, 'Legacy Forger', 5000000, 'PNG/LF.png', '#00CED1'),
            (9, 'Alpha Legend', 20000000, 'PNG/AL.png', '#FF2222')
        ]
        
        for r in ranks:
            lvl, name, min_xp, icon, color = r
            c.execute('''
                INSERT INTO user_ranks (user_id, level, name, min_xp, icon, color)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (admin_id, lvl, name, min_xp, icon, color))
            
    conn.commit()
    print("Admin migration complete.")

def main():
    conn = init_db()
    migrate_admin_data(conn)
    if conn: conn.close()
    print("=== Dynamic Migration Complete ===")

if __name__ == "__main__":
    main()