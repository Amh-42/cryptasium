"""
Migration script to add custom_name column to rank_conditions table.
"""
from app import create_app
from models import db
from sqlalchemy import text

def migrate():
    app = create_app()
    
    with app.app_context():
        print("Starting custom_name migration for rank_conditions...")
        
        try:
            # Check if column exists
            print("Checking if custom_name column exists...")
            result = db.session.execute(text("PRAGMA table_info(rank_conditions)"))
            columns = [row[1] for row in result]
            
            if 'custom_name' not in columns:
                print("Adding custom_name column...")
                db.session.execute(text("ALTER TABLE rank_conditions ADD COLUMN custom_name VARCHAR(100)"))
                db.session.commit()
                print("✓ Column custom_name added successfully")
            else:
                print("✓ Column custom_name already exists")
                
            print("\n✅ Migration complete!")
            
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ Error during migration: {str(e)}")

if __name__ == '__main__':
    migrate()
