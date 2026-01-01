"""
Database migration script for Dashboard Customization.
Adds dashboard_images table and show_dashboard_header column.
Run: python migrate_dashboard.py
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models import db

def migrate():
    """Run database migrations for dashboard customization"""
    print("\n=== Running Dashboard Migrations ===\n")
    
    app = create_app()
    
    with app.app_context():
        # Get raw connection for executing ALTER TABLE
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        try:
            # 1. Add show_dashboard_header to user_settings
            try:
                print("Adding show_dashboard_header column to user_settings...")
                cursor.execute("ALTER TABLE user_settings ADD COLUMN show_dashboard_header BOOLEAN DEFAULT 1")
                connection.commit()
                print("[OK] Added show_dashboard_header")
            except Exception as e:
                if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                    print("[SKIP] show_dashboard_header already exists")
                else:
                    print(f"[ERROR] Failed to add column: {e}")

            # 2. Create dashboard_images table
            # We'll use db.create_all() which skips existing tables, so we just need to make sure the model is loaded (it is via app imports)
            print("Creating dashboard_images table if not exists...")
            db.create_all()
            print("[OK] Database schema updated")
            
        except Exception as e:
            print(f"[FATAL ERROR] {e}")
        finally:
            cursor.close()
            connection.close()
        
        print("\n=== Migration Complete ===\n")

if __name__ == '__main__':
    migrate()
