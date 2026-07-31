#!/usr/bin/env python3
"""
IT 资产管理系统资产管理系统 · 硬件信息恢复脚本 v1.0
=============================================
用途：从Excel台账的「备注」字段中解析CPU/内存/硬盘信息，
      回填到数据库的 cpu/memory/disk 列。

典型备注格式：
  - "M1 16G 512G"        → cpu=M1, memory=16G, disk=512G
  - "i5 8G 256G"         → cpu=i5, memory=8G, disk=256G
  - "M5 Pro 24GB 1TB"    → cpu=M5 Pro, memory=24GB, disk=1TB

执行：
  python3 recover_hardware_info.py
"""
import sqlite3, openpyxl, re
from datetime import datetime

EXCEL = "input.xlsx"
DB = "os.path.join(os.path.dirname(__file__), 'data', 'assets.db')"

# 备注中硬件信息的常见格式：CPU 内存 存储
HW_PATTERN = re.compile(
    r'(M\d(?:\s+Pro)?|i[3-9]-?\d{4,5}[A-Z]?[A-Z]?|i[3-9]|Ryzen\s*\d|'
    r'奔腾|赛扬|N\d{3}|酷睿)'
    r'.*?(\d+\s*(?:G|GB))\s+(\d+\s*(?:G|GB|T|TB))',
    re.IGNORECASE
)

def parse_hw_from_text(text):
    """从文本中提取硬件信息，返回 (cpu, memory, disk) 元组"""
    if not text:
        return None
    m = HW_PATTERN.search(text)
    if m:
        cpu = m.group(1).strip()
        mem = m.group(2).strip().upper().replace(' ', '')
        disk = m.group(3).strip().upper().replace(' ', '')
        return (cpu, mem, disk)
    return None

def main():
    wb = openpyxl.load_workbook(EXCEL, data_only=True)
    conn = sqlite3.connect(DB, timeout=30)
    cur = conn.cursor()

    stats = {"scanned": 0, "recovered": 0, "skipped": 0}

    for sn in wb.sheetnames:
        if sn == '汇总_整表大盘':
            continue
        ws = wb[sn]
        for row in ws.iter_rows(min_row=2, values_only=True):
            asset_id = str(row[1]).strip() if row[1] else ''
            if not asset_id or asset_id == 'None':
                continue

            stats["scanned"] += 1

            # 检查数据库是否已有有效硬件信息
            cur.execute("SELECT cpu, memory, disk FROM assets WHERE asset_id = ?", (asset_id,))
            db_row = cur.fetchone()
            if not db_row:
                continue

            db_cpu, db_mem, db_disk = (db_row[0] or ''), (db_row[1] or ''), (db_row[2] or '')

            # 如果数据库已有有效数据，跳过
            if db_cpu and db_mem and db_disk:
                stats["skipped"] += 1
                continue
            if db_cpu and db_mem and not db_disk:
                # Disk empty but others ok - try to find disk
                pass  # allow partial recovery

            # 优先从备注(Col 26)提取，回退到型号(Col 5)
            remarks = str(row[26]).strip() if row[26] else ''
            model = str(row[5]).strip() if row[5] else ''

            hw = parse_hw_from_text(remarks) or parse_hw_from_text(model)
            if not hw:
                stats["skipped"] += 1
                continue

            cpu, mem, disk = hw
            updates = {}
            if not db_cpu:
                updates["cpu"] = cpu
            if not db_mem:
                updates["memory"] = mem
            if not db_disk:
                updates["disk"] = disk

            if updates:
                sql = ", ".join(f"{k}=?" for k in updates)
                vals = list(updates.values()) + [asset_id]
                cur.execute(f"UPDATE assets SET {sql} WHERE asset_id=?", vals)
                conn.commit()

                # 记录审计日志
                detail = f"硬件恢复: {' '.join(f'{k}={v}' for k,v in updates.items())}"
                cur.execute(
                    "INSERT INTO operation_log(timestamp,asset_id,operation,operator,details) VALUES(?,?,'IMPORT','硬件恢复',?)",
                    (datetime.now().isoformat(), asset_id, detail)
                )
                conn.commit()

                stats["recovered"] += 1
                print(f"  ✅ {asset_id}: {updates}")

    conn.close()
    print(f"\n📊 扫描: {stats['scanned']} | 恢复: {stats['recovered']} | 跳过: {stats['skipped']}")

if __name__ == "__main__":
    main()
