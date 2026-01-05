import sqlite3
import os
from datetime import datetime

def migrate():
    db_path = os.path.join('instance', 'cryptasium.db')
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # check current_rank_id
    print("Checking for current_rank_id column in users...")
    try:
        cursor.execute("SELECT current_rank_id FROM users LIMIT 1")
        print("Column 'current_rank_id' already exists.")
    except sqlite3.OperationalError:
        print("Adding 'current_rank_id' column to users...")
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN current_rank_id INTEGER REFERENCES custom_ranks(id)")
            conn.commit()
            print("Successfully added current_rank_id.")
        except Exception as e:
            print(f"Error adding current_rank_id: {e}")

    # check rank_changed_at
    print("Checking for rank_changed_at column in users...")
    try:
        cursor.execute("SELECT rank_changed_at FROM users LIMIT 1")
        print("Column 'rank_changed_at' already exists.")
    except sqlite3.OperationalError:
        print("Adding 'rank_changed_at' column to users...")
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN rank_changed_at DATE")
            conn.commit()
            print("Successfully added rank_changed_at.")
        except Exception as e:
            print(f"Error adding rank_changed_at: {e}")

    conn.close()

if __name__ == '__main__':
    migrate()
