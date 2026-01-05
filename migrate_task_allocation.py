import sqlite3
import os

def migrate():
    db_path = os.path.join('instance', 'cryptasium.db')
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("Checking for allocated_condition_id column in task_completions...")
    try:
        cursor.execute("SELECT allocated_condition_id FROM task_completions LIMIT 1")
        print("Column 'allocated_condition_id' already exists.")
    except sqlite3.OperationalError:
        print("Adding 'allocated_condition_id' column to task_completions...")
        try:
            cursor.execute("ALTER TABLE task_completions ADD COLUMN allocated_condition_id INTEGER REFERENCES rank_conditions(id)")
            conn.commit()
            print("Successfully added column.")
        except Exception as e:
            print(f"Error adding column: {e}")

    conn.close()

if __name__ == '__main__':
    migrate()
