import openpyxl

EXCEL_PATH = 'input.xlsx'

def check_discrepancy():
    wb = openpyxl.load_workbook(EXCEL_PATH, read_only=True, data_only=True)
    
    # 获取明细表中的总数
    detail_count = 0
    for sheet_name in wb.sheetnames:
        if '在用' in sheet_name or '空闲' in sheet_name:
            ws = wb[sheet_name]
            for row in ws.iter_rows(min_row=2, values_only=True):
                if row and len(row) > 1 and row[1]:
                    detail_count += 1
                    
    print(f"明细 Sheet (各城市在用/空闲) 统计的资产条数总计: {detail_count}\n")
    
    # 获取汇总表中的总数
    ws_summary = wb['汇总_整表大盘']
    print("--- 第一页：汇总_整表大盘 ---")
    header = [str(cell).strip() if cell else '' for cell in next(ws_summary.iter_rows(min_row=1, max_row=1, values_only=True))]
    print("表头:", header)
    
    summary_total = 0
    for row_idx, row in enumerate(ws_summary.iter_rows(min_row=2, values_only=True), 2):
        if not row[0]: # 城市为空跳过
            break
        # 假设最后一列（或者名为'合计'的列）是总计
        total_idx = header.index('合计') if '合计' in header else len(row) - 1
        city_status_total = int(row[total_idx] or 0)
        summary_total += city_status_total
        print(f"行 {row_idx}: {row[0]} ({row[1]}) -> 汇总数量: {city_status_total}")
        
    print(f"\n第一页汇总表计算的资产总计: {summary_total}")
    print(f"差值: {summary_total - detail_count} 条")

if __name__ == "__main__":
    check_discrepancy()