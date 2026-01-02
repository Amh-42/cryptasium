import sqlite3
import os

def migrate():
    db_path = os.path.join('instance', 'cryptasium.db')
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Column additions
    migrations = [
        ("rank_conditions", "is_bucket", "BOOLEAN DEFAULT 0"),
        ("trackable_entries", "allocated_condition_id", "INTEGER")
    ]

    for table, column, col_type in migrations:
        try:
            print(f"Adding column {column} to {table} table...")
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
            conn.commit()
            print(f"Successfully added {column} to {table}.")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print(f"Column {column} already exists in {table}. Skipping.")
            else:
                print(f"Failed to add {column} to {table}: {e}")

    conn.close()

if __name__ == '__main__':
    migrate()
