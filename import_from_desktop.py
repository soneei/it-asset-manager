"""
资产台账清洗导入脚本
从桌面资产清单Excel清洗数据并导入资产管理系统

用法：python import_from_desktop.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from openpyxl import load_workbook
from datetime import datetime
from asset_manager import AssetManager, Asset, init_db

# Excel列索引（从1开始，与openpyxl一致）
COL_MAPPING = {
    'asset_id': 2,        # 资产编码
    'name': 3,            # 资产名称
    'brand': 5,           # 品牌（格式：类型/品牌）
    'model': 6,           # 型号
    'serial_number': 7,    # 序列号
    'supplier': 9,        # 供应商
    'purchase_price': 10,  # 采购价格（原值）
    'purchase_date': 17,  # 采购日期
    'depreciation_years': 22,  # 折旧年限
    'warranty_expire': 23, # 质保到期日
    'location': 27,       # 地点
    'department': 29,     # 部门
    'assignee': 30,       # 使用人
    'asset_type_name': 35,# 资产类型名称
    'storage': 42,        # 存储容量
    'memory': 43,         # 内存
    'cpu': 44,            # CPU
    'mac_address': 41,    # MAC地址
}

def infer_asset_type(name: str, brand: str, model: str) -> str:
    """根据名称/品牌/型号推断资产类型"""
    text = f"{name} {brand} {model}".lower()

    if 'macbook' in text or 'laptop' in text or '笔记本' in text:
        return 'laptop'
    elif 'macmini' in text or 'mac mini' in text or '台式机' in text or '台式' in text:
        return 'desktop'
    elif 'imac' in text:
        return 'desktop'
    elif '显示器' in text or 'monitor' in text or 'dell p' in text:
        return 'monitor'
    elif 'iphone' in text or '手机' in text:
        return 'phone'
    elif 'ipad' in text or '平板' in text:
        return 'tablet'
    elif '键盘' in text or 'mouse' in text or '鼠标' in text:
        return 'keyboard_mouse'
    elif '打印机' in text or 'print' in text:
        return 'printer'
    else:
        return 'other'

def parse_brand_supplier(brand_str: str) -> tuple:
    """解析品牌供应商字符串，格式：供应商/品牌 或 仅品牌"""
    if not brand_str:
        return '', ''
    parts = str(brand_str).split('/')
    if len(parts) >= 2:
        return parts[-1].strip(), parts[0].strip()  # 品牌, 供应商
    return brand_str.strip(), ''

def clean_value(val) -> str:
    """清洗单元格值"""
    if val is None:
        return ''
    return str(val).strip()

def clean_price(val) -> float:
    """清洗价格"""
    if val is None:
        return 0.0
    try:
        return float(val)
    except:
        return 0.0

def parse_date(val) -> str:
    """解析日期格式 YYYY/MM/DD -> YYYY-MM-DD"""
    if not val:
        return ''
    val_str = str(val)
    # 处理 YYYY/MM/DD 格式
    if '/' in val_str:
        parts = val_str.split('/')
        if len(parts) == 3:
            return f"{parts[0]}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"
    # 处理 YYYY-MM-DD 格式
    if '-' in val_str and len(val_str) == 10:
        return val_str
    return val_str

def import_assets_from_excel(excel_path: str, operator: str = "系统导入") -> dict:
    """从Excel导入资产数据"""
    print(f"[导入] 正在读取：{excel_path}")

    wb = load_workbook(excel_path, data_only=True)
    ws = wb.worksheets[0]  # 第一个sheet

    print(f"[导入] 工作表：{ws.title}，行数：{ws.max_row - 1}，列数：{ws.max_column}")

    assets_data = []
    skipped = 0
    errors = []

    # 遍历数据行（跳过表头）
    for row_num in range(2, ws.max_row + 1):
        try:
            # 提取各列数据
            def get_col(idx):
                return ws.cell(row=row_num, column=idx).value

            asset_id = clean_value(get_col(COL_MAPPING['asset_id']))
            if not asset_id or asset_id.startswith('资产编码'):  # 跳过空行和标题行
                continue

            name = clean_value(get_col(COL_MAPPING['name']))
            brand_supplier = clean_value(get_col(COL_MAPPING['brand']))
            model = clean_value(get_col(COL_MAPPING['model']))
            serial_number = clean_value(get_col(COL_MAPPING['serial_number']))
            purchase_price = clean_price(get_col(COL_MAPPING['purchase_price']))
            purchase_date = parse_date(get_col(COL_MAPPING['purchase_date']))
            depreciation_years = int(clean_value(get_col(COL_MAPPING['depreciation_years'])) or 3)
            warranty_expire = parse_date(get_col(COL_MAPPING['warranty_expire']))
            department = clean_value(get_col(COL_MAPPING['department']))
            assignee = clean_value(get_col(COL_MAPPING['assignee']))
            location = clean_value(get_col(COL_MAPPING['location']))
            storage = clean_value(get_col(COL_MAPPING['storage']))
            memory = clean_value(get_col(COL_MAPPING['memory']))
            cpu = clean_value(get_col(COL_MAPPING['cpu']))
            mac_address = clean_value(get_col(COL_MAPPING['mac_address']))

            # 解析品牌和供应商
            brand, supplier = parse_brand_supplier(brand_supplier)
            if not supplier:
                supplier = clean_value(get_col(COL_MAPPING['supplier']))

            # 推断资产类型
            asset_type = infer_asset_type(name, brand, model)

            # 构建资产名称（如果没有就用型号）
            if not name:
                name = model if model else f"{brand} {model}"

            # 推断状态
            status = 'in_use' if assignee else 'in_stock'

            # 构造资产数据
            asset_dict = {
                'asset_id': asset_id,
                'barcode': '',
                'name': name,
                'asset_type': asset_type,
                'brand': brand,
                'model': model,
                'serial_number': serial_number,
                'status': status,
                'assignee': assignee,
                'department': department,
                'seat_number': '',
                'location': location,
                'purchase_date': purchase_date,
                'purchase_price': purchase_price,
                'supplier': supplier,
                'warranty_expire': warranty_expire,
                'depreciation_years': depreciation_years,
                'mac_address': mac_address,
                'remarks': f"存储:{storage} 内存:{memory} CPU:{cpu}".strip(),
            }

            assets_data.append(asset_dict)

        except Exception as e:
            errors.append(f"第{row_num}行：{str(e)}")

    print(f"[导入] 清洗完成，待导入：{len(assets_data)}条")

    # 导入数据库
    if assets_data:
        init_db()
        manager = AssetManager(operator)
        result = manager.import_batch(assets_data)
        print(f"[导入] 结果：{result['message']}")
        if result['errors']:
            print(f"[导入] 错误列表（前10条）：")
            for err in result['errors'][:10]:
                print(f"  - {err}")
        return result
    else:
        return {'success': False, 'message': '没有可导入的数据'}


if __name__ == "__main__":
    # 默认桌面路径
    desktop = os.path.expanduser("~/Desktop")
    excel_path = os.path.join(desktop, "input.xlsx")

    if len(sys.argv) > 1:
        excel_path = sys.argv[1]

    if not os.path.exists(excel_path):
        print(f"[错误] 文件不存在：{excel_path}")
        sys.exit(1)

    result = import_assets_from_excel(excel_path)
    print(f"\n[完成] 导入结果：{result}")
