import sqlite3
import os

def migrate():
    db_path = os.path.join('instance', 'cryptasium.db')
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("Checking for expense_threshold column in trackable_types...")
    try:
        cursor.execute("SELECT expense_threshold FROM trackable_types LIMIT 1")
        print("Column 'expense_threshold' already exists.")
    except sqlite3.OperationalError:
        print("Adding 'expense_threshold' column to trackable_types...")
        try:
            cursor.execute("ALTER TABLE trackable_types ADD COLUMN expense_threshold FLOAT DEFAULT 0")
            conn.commit()
            print("Successfully added column.")
        except Exception as e:
            print(f"Error adding column: {e}")

    conn.close()

if __name__ == '__main__':
    migrate()
