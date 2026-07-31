#!/usr/bin/env python3
"""
IT 资产管理系统资产管理系统 · 数据全面校准迁移脚本 v1.0
=============================================
用途：从Excel台账重新校正数据库中所有资产的硬件信息（CPU/内存/硬盘）
      以及其他关键字段（部门、位置、使用人、品牌、型号、序列号等）

执行方式：
  cd <项目根目录>
  python3 migrate_asset_data.py

说明：
  - 以Excel台账为权威数据源，逐条匹配 asset_id
  - 仅更新Excel中有数据、数据库中为空或有误的字段
  - 不删除/覆盖数据库中Excel没有的资产
  - 所有修改记录到 operation_log
=============================================
"""
import sqlite3
import openpyxl
import json
from datetime import datetime

# ── 配置 ──────────────────────────────────────────────────────────
EXCEL_PATH = "input.xlsx"
DB_PATH = "os.path.join(os.path.dirname(__file__), 'data', 'assets.db')"
JSON_PATH = "os.path.join(os.path.dirname(__file__), 'data', 'assets.json')"

# Excel各sheet与城市/状态的映射
SHEET_MAP = {
    "北京_在用": {"city": "北京", "status": "in_use"},
    "北京_空闲": {"city": "北京", "status": "in_stock"},
    "上海_在用": {"city": "上海", "status": "in_use"},
    "上海_空闲": {"city": "上海", "status": "in_stock"},
    "厦门_在用": {"city": "厦门", "status": "in_use"},
    "厦门_空闲": {"city": "厦门", "status": "in_stock"},
    "广州_在用": {"city": "广州", "status": "in_use"},
    "广州_空闲": {"city": "广州", "status": "in_stock"},
    "其他城市_在用": {"city": None, "status": "in_use"},
    "其他城市_空闲": {"city": None, "status": "in_stock"},
}

# Excel列号 → 数据库字段映射（列号从0开始）
COL_MAP = {
    1: "asset_id",       # 资产编码
    2: "name",            # 资产名称
    3: "asset_type_cn",   # 资产分类（中文，需映射）
    4: "brand",           # 品牌
    5: "model",           # 型号
    6: "serial_number",   # 设备序列号
    7: "company",         # 所属公司
    8: "assignee",        # 使用人
    12: "department",     # 使用部门
    14: "purchase_date",  # 领用日期
    16: "purchase_date_actual",  # 购置日期
    17: "location",       # 所在位置
    24: "unit",           # 计量单位
    25: "order_number",   # 订单号
    26: "remarks",        # 备注
    28: "supplier",       # 供应商
    32: "warranty_expire",# 维保到期
    35: "purchase_price", # 金额
    41: "disk",           # 硬盘 ← 硬件信息
    42: "memory",         # 内存 ← 硬件信息
    43: "cpu",            # CPU型号 ← 硬件信息
}

# 资产类型中文→英文映射
TYPE_MAP = {
    "台式机": "desktop", "笔记本": "laptop", "笔记本电脑": "laptop",
    "苹果笔记本电脑": "laptop", "苹果一体机": "desktop", "苹果主机": "desktop",
    "显示器": "monitor", "戴尔显示器": "monitor", "LG显示器": "monitor",
    "小米笔记本电脑": "laptop", "联想笔记本电脑": "laptop",
    "戴尔笔记本电脑": "laptop", "戴尔主机": "other", "其他品牌主机": "other",
    "其他笔记本电脑": "laptop", "其他显示器": "monitor",
    "手机": "phone", "平板": "tablet", "键鼠": "keyboard_mouse",
    "打印机": "printer", "其他": "other", "一体机": "desktop", "主机": "other",
}

def main():
    print("=" * 60)
    print("IT 资产管理系统资产管理系统 · 数据全面校准迁移")
    print(f"源文件: {EXCEL_PATH}")
    print(f"目标库: {DB_PATH}")
    print(f"开始时间: {datetime.now().isoformat()}")
    print("=" * 60)

    # 1. 读取Excel
    wb = openpyxl.load_workbook(EXCEL_PATH, data_only=True)
    
    excel_data = []  # [{asset_id: ..., field: value, ...}]
    for sheet_name, meta in SHEET_MAP.items():
        if sheet_name not in wb.sheetnames:
            print(f"  ⚠️ 跳过不存在的sheet: {sheet_name}")
            continue
        ws = wb[sheet_name]
        rows = list(ws.iter_rows(min_row=2, values_only=True))
        print(f"  📄 {sheet_name}: {len(rows)} 条")
        
        for row in rows:
            asset_id = str(row[1]).strip() if row[1] else None
            if not asset_id or asset_id == "None":
                continue
            
            item = {"asset_id": asset_id, "source_sheet": sheet_name}
            if meta["city"]:
                item["location"] = meta["city"]
            item["status"] = meta["status"]
            
            # 解析各字段
            for col_idx, field in COL_MAP.items():
                val = row[col_idx] if col_idx < len(row) else None
                if val is not None:
                    s = str(val).strip()
                    if s and s != "None":
                        item[field] = s
                    else:
                        item[field] = None
                else:
                    item[field] = None
            
            # 类型映射
            cn_type = item.pop("asset_type_cn", None)
            if cn_type:
                item["asset_type"] = TYPE_MAP.get(cn_type, "other")
            
            excel_data.append(item)
    
    print(f"\n  📊 共读取 {len(excel_data)} 条资产记录")
    
    # 2. 连接数据库
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    cur = conn.cursor()
    
    # 3. 逐条比对更新
    stats = {"matched": 0, "updated": 0, "not_found": 0, "hw_fixed": 0}
    
    for item in excel_data:
        asset_id = item["asset_id"]
        cur.execute("SELECT asset_id, cpu, memory, disk, brand, model, serial_number, department, location FROM assets WHERE asset_id = ?", (asset_id,))
        db_row = cur.fetchone()
        
        if not db_row:
            stats["not_found"] += 1
            continue
        
        stats["matched"] += 1
        
        # 需要更新的字段
        updates = {}
        hw_fields = ["cpu", "memory", "disk"]  # 硬件信息重点核查
        all_fields = ["cpu", "memory", "disk", "brand", "model", "serial_number", "department", "location", "name"]
        
        for field in all_fields:
            if field in item and item[field]:
                db_val = db_row[field] if field in [c[0] for c in cur.description] else None
                # 如果数据库的硬件信息明显错误（如"台"/"采购"/日期等），强制覆盖
                if field in hw_fields:
                    # 硬件的正确值不应该包含这些
                    bad_values = ["台", "采购", "领用", "空闲", "正常"]
                    is_bad_db = db_val in bad_values or (db_val and any(b in str(db_val) for b in bad_values))
                    # 检查是否是日期格式
                    if db_val and len(str(db_val)) == 10 and str(db_val).count("-") + str(db_val).count("/") >= 1:
                        is_bad_db = True
                    
                    if is_bad_db or not db_val:
                        updates[field] = item[field]
                else:
                    # 非硬件字段：仅数据库为空时更新
                    if not db_val or str(db_val).strip() in ("", "None"):
                        updates[field] = item[field]
        
        if updates:
            set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
            vals = list(updates.values()) + [asset_id]
            cur.execute(f"UPDATE assets SET {set_clause} WHERE asset_id = ?", vals)
            conn.commit()
            stats["updated"] += 1
            
            hw_updated = any(k in hw_fields for k in updates.keys())
            if hw_updated:
                stats["hw_fixed"] += 1
            
            if hw_updated:
                detail = f"硬件校准: {', '.join(f'{k}={v}' for k, v in updates.items() if k in hw_fields)}"
            else:
                detail = f"字段更新: {', '.join(updates.keys())}"
            
            cur.execute("""
                INSERT INTO operation_log (timestamp, asset_id, operation, operator, details)
                VALUES (?, ?, 'IMPORT', '数据校准', ?)
            """, (datetime.now().isoformat(), asset_id, detail))
            conn.commit()
    
    conn.close()
    
    # 4. 同步JSON
    try:
        with open(JSON_PATH, 'r') as f:
            all_json = json.load(f)
        # 找出JSON中也需要更新的记录
        json_updated = 0
        for j in all_json:
            for item in excel_data:
                if j.get("asset_id") == item["asset_id"]:
                    for field in all_fields:
                        if field in item and item[field]:
                            if field in hw_fields:
                                j[field] = item[field]
                            elif not j.get(field):
                                j[field] = item[field]
                    json_updated += 1
                    break
        with open(JSON_PATH, 'w') as f:
            json.dump(all_json, f, ensure_ascii=False, indent=2)
        print(f"\n  ✅ JSON同步: {json_updated} 条")
    except Exception as e:
        print(f"\n  ⚠️ JSON同步失败: {e}")
    
    # 5. 报告
    print("\n" + "=" * 60)
    print("校准完成报告")
    print("=" * 60)
    print(f"  Excel匹配到: {stats['matched']} 条")
    print(f"  已更新字段:  {stats['updated']} 条")
    print(f"  硬件已修复:  {stats['hw_fixed']} 条")
    print(f"  Excel有但DB无: {stats['not_found']} 条（需手动入库）")
    print(f"  完成时间: {datetime.now().isoformat()}")
    print("=" * 60)

if __name__ == "__main__":
    main()
