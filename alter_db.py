import sqlite3
import os

DB_PATH = "os.path.join(os.path.dirname(__file__), 'data', 'assets.db')"

def alter_schema():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 检查哪些列需要加
    cursor.execute("PRAGMA table_info(assets)")
    columns = [info[1] for info in cursor.fetchall()]
    
    # 要新增的列
    new_cols = {
        'cpu': 'TEXT',
        'memory': 'TEXT',
        'disk': 'TEXT',
        'order_number': 'TEXT',
        'oa_payment_number': 'TEXT'
    }
    
    for col, ctype in new_cols.items():
        if col not in columns:
            try:
                conn.execute(f"ALTER TABLE assets ADD COLUMN {col} {ctype}")
                print(f"Added column {col}")
            except Exception as e:
                print(f"Failed to add {col}: {e}")
                
    conn.commit()
    conn.close()
    print("Schema updated successfully.")

if __name__ == "__main__":
    alter_schema()