import sqlite3
import os

def inspect():
    db_path = os.path.join('instance', 'cryptasium.db')
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("Columns in trackable_types:")
    cursor.execute("PRAGMA table_info(trackable_types)")
    columns = cursor.fetchall()
    for col in columns:
        print(f"ID: {col[0]}, Name: {col[1]}, Type: {col[2]}")

    conn.close()

if __name__ == '__main__':
    inspect()
