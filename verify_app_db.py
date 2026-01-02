from app import create_app
from models import db, TrackableType
from sqlalchemy import text

app = create_app()

with app.app_context():
    print(f"Database URI: {app.config['SQLALCHEMY_DATABASE_URI']}")
    
    try:
        # Try queried through model
        count = TrackableType.query.count()
        print(f"Successfully queried TrackableType. Total count: {count}")
        
        # Try specific column via model
        first = TrackableType.query.first()
        if first:
            print(f"First trackable: {first.name}, expense_threshold: {first.expense_threshold}")
        else:
            print("No trackables found in database.")
            
    except Exception as e:
        print(f"Error querying via model: {e}")
        
    try:
        # Try raw SQL
        with db.engine.connect() as conn:
            result = conn.execute(text("SELECT expense_threshold FROM trackable_types LIMIT 1"))
            print("Successfully queried expense_threshold via raw SQL.")
    except Exception as e:
        print(f"Error querying via raw SQL: {e}")
