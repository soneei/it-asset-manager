import openpyxl
import sqlite3
import datetime

DB_PATH = "os.path.join(os.path.dirname(__file__), 'data', 'assets.db')"
EXCEL_PATH = 'input.xlsx'

def enrich_data():
    conn = sqlite3.connect(DB_PATH)
    wb = openpyxl.load_workbook(EXCEL_PATH, read_only=True, data_only=True)
    
    updated_count = 0
    
    for sheet_name in wb.sheetnames:
        if '在用' not in sheet_name and '空闲' not in sheet_name:
            continue
            
        ws = wb[sheet_name]
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row or len(row) < 2 or not row[1]:
                continue
                
            asset_id = str(row[1]).strip()
            
            # 提取高级配置
            order_number = str(row[25] or '').strip() if len(row) > 25 else ''
            supplier = str(row[28] or '').strip() if len(row) > 28 else ''
            warranty = str(row[32] or '').strip() if len(row) > 32 else ''
            disk = str(row[41] or '').strip() if len(row) > 41 else ''
            memory = str(row[42] or '').strip() if len(row) > 42 else ''
            cpu = str(row[43] or '').strip() if len(row) > 43 else ''
            oa_num = str(row[44] or '').strip() if len(row) > 44 else ''
            
            # 更新已存在的数据
            conn.execute('''
                UPDATE assets 
                SET order_number=?, supplier=?, warranty_expire=?, disk=?, memory=?, cpu=?, oa_payment_number=?
                WHERE asset_id=?
            ''', (order_number, supplier, warranty, disk, memory, cpu, oa_num, asset_id))
            
            updated_count += 1
            
    conn.commit()
    conn.close()
    print(f"Successfully enriched {updated_count} rows with hardware specs.")

if __name__ == "__main__":
    enrich_data()