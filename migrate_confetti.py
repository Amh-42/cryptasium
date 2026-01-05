import sqlite3
from app import create_app

def add_confetti_column():
    app = create_app()
    with app.app_context():
        conn = sqlite3.connect('cryptasium.db')
        cursor = conn.cursor()
    
    try:
        print("Checking if column 'always_show_confetti' exists...")
        cursor.execute("SELECT always_show_confetti FROM users LIMIT 1")
        print("Column already exists.")
    except sqlite3.OperationalError:
        print("Column missing. Adding 'always_show_confetti'...")
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN always_show_confetti BOOLEAN DEFAULT 0")
            conn.commit()
            print("Successfully added column.")
        except Exception as e:
            print(f"Error adding column: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    add_confetti_column()
