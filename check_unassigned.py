import sqlite3

DB_PATH = "os.path.join(os.path.dirname(__file__), 'data', 'assets.db')"

def check_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT * FROM assets WHERE assignee = '未分配' OR assignee = '' LIMIT 5")
    rows = cursor.fetchall()
    for row in rows:
        print(dict(row))

if __name__ == "__main__":
    check_db()
