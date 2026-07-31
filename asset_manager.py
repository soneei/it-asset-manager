"""
IT 资产管理系统资产管理系统 MVP v1.0
全生命周期资产管理 | SQLite + JSON双存储 | COBIT + ITIL框架

标准依据：
- ISO/IEC 19770-1 (IT资产管理体系)
- COBIT APO17 (资产管理)
- ITIL v4 (服务价值体系)
"""

import sqlite3
import json
import os
import uuid
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict, field
from enum import Enum

# ============ 项目路径 ============
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
DB_PATH = os.path.join(DATA_DIR, "assets.db")
JSON_PATH = os.path.join(DATA_DIR, "assets.json")

os.makedirs(DATA_DIR, exist_ok=True)


# ============ 生命周期状态枚举 ============
class AssetStatus(Enum):
    """资产全生命周期六阶段（基于ISO/IEC 38500治理框架）"""
    IN_STOCK = "in_stock"           # ① 入库/库存
    IN_USE = "in_use"                # ② 领用/在用
    TRANSFERRED = "transferred"      # ③ 调拨中
    UNDER_REPAIR = "under_repair"    # ④ 维保/检修
    IDLE = "idle"                    # ⑤ 闲置封存
    DISPOSED = "disposed"            # ⑥ 处置/退出

    @property
    def label(self) -> str:
        labels = {
            "in_stock": "库存",
            "in_use": "在用",
            "transferred": "调拨中",
            "under_repair": "维保中",
            "idle": "闲置",
            "disposed": "已处置",
        }
        return labels.get(self.value, self.value)

    @property
    def step(self) -> int:
        steps = {"in_stock": 1, "in_use": 2, "transferred": 3,
                 "under_repair": 4, "idle": 5, "disposed": 6}
        return steps.get(self.value, 0)


class AssetType(Enum):
    """资产类型枚举"""
    LAPTOP = "laptop"          # 笔记本电脑
    DESKTOP = "desktop"        # 台式机
    MONITOR = "monitor"        # 显示器
    PHONE = "phone"            # 手机
    TABLET = "tablet"          # 平板
    KEYBOARD_MOUSE = "km"      # 键鼠套装
    PRINTER = "printer"         # 打印机
    OTHER = "other"            # 其他

    @property
    def label(self) -> str:
        labels = {
            "laptop": "笔记本电脑",
            "desktop": "台式机",
            "monitor": "显示器",
            "phone": "手机",
            "tablet": "平板",
            "km": "键鼠套装",
            "printer": "打印机",
            "other": "其他",
        }
        return labels.get(self.value, self.value)


class DisposalMethod(Enum):
    """处置方式"""
    SCRAP = "scrap"            # 报废
    DONATE = "donate"          # 捐赠
    RESELL = "resell"          # 二手回收
    RETURN = "return"          # 退租/退还

    @property
    def label(self) -> str:
        labels = {"scrap": "报废", "donate": "捐赠", "resell": "二手回收", "return": "退租/退还"}
        return labels.get(self.value, self.value)


# ============ 操作类型枚举（审计用）============
class OperationType:
    """可审计操作类型（用于operation_log的operation字段）
    ISO/IEC 19770-1审计合规要求：每个操作必须有明确的操作类型和操作人
    """
    新增入库 = "入库"
    领用 = "领用"
    调拨 = "调拨"
    闲置封存 = "闲置封存"
    维保登记 = "维保登记"
    处置 = "处置/退出"
    彻底删除 = "彻底删除"
    信息更新 = "信息更新"
    批量导入 = "批量导入"
    序列号更新 = "更新序列号"
    状态变更 = "状态变更"  # 通用兜底


# ============ 资产数据模型 ============
@dataclass
class Asset:
    """
    资产标准数据模型
    参考 ISO/IEC 19770-1 + COBIT CMDB CI设计
    预留TCO全成本字段
    """
    # === 基础标识 ===
    asset_id: str = ""                 # 资产编码（系统生成，格式：MY-年份-序号）
    barcode: str = ""                  # 条码/二维码编号
    name: str = ""                     # 资产名称
    asset_type: str = ""               # 资产类型 (AssetType枚举值)
    brand: str = ""                    # 品牌
    model: str = ""                    # 型号
    serial_number: str = ""            # 序列号/SN

    # === 生命周期状态 ===
    status: str = "in_stock"           # 当前状态 (AssetStatus枚举值)
    status_history: List[Dict] = field(default_factory=list)  # 状态变更历史

    # === 归属信息 ===
    assignee: str = ""                 # 使用人
    department: str = ""               # 使用部门
    seat_number: str = ""              # 工位号
    location: str = ""                 # 所在地点

    # === 采购与财务（预留TCO字段）===
    purchase_date: str = ""           # 采购日期
    purchase_price: float = 0.0        # 采购价格（元）
    supplier: str = ""                 # 供应商
    warranty_expire: str = ""          # 质保到期日
    depreciation_years: int = 3        # 折旧年限（默认3年）

    # === 运营信息 ===
    mac_address: str = ""              # MAC地址
    ip_address: str = ""               # IP地址
    os_version: str = ""               # 操作系统版本
    software_list: List[str] = field(default_factory=list)  # 已装软件列表

    # === 系统管理字段 ===
    created_at: str = ""               # 创建时间
    updated_at: str = ""               # 更新时间
    operator: str = ""                 # 操作人
    remarks: str = ""                 # 备注

    def __post_init__(self):
        if not self.asset_id:
            self.asset_id = self._generate_id()
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()

    def _generate_id(self) -> str:
        """生成资产编码：MY-年份-4位序号"""
        year = datetime.now().year
        # 查询当前最大序号
        conn = _get_db()
        cur = conn.execute(
            "SELECT COUNT(*) FROM assets WHERE asset_id LIKE ?",
            (f"MY-{year}-%",)
        )
        count = cur.fetchone()[0]
        conn.close()
        seq = (count + 1)
        return f"MY-{year}-{seq:04d}"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @property
    def current_depreciation(self) -> float:
        """计算当前折旧值（直线折旧法，直线法/Straight-Line Depreciation）。

        财务安全说明：折旧失败（缺日期/价格、折旧年限为0、日期格式错）时，
        不再静默返回原价伪装成"全新未折旧"，而是记 warning 日志后返回原价，
        调用方需意识到该值不可信（建议结合 depreciation_reliable 判断）。
        """
        import logging
        if not self.purchase_date or not self.purchase_price:
            return 0.0
        if not self.depreciation_years:
            logging.warning(f"[折旧] 资产 {self.asset_id} 折旧年限为0/缺失，按未折旧返回原价（值不可信）")
            return float(self.purchase_price)
        try:
            purchase = datetime.strptime(self.purchase_date, "%Y-%m-%d")
            years_used = (date.today() - purchase.date()).days / 365.0
            annual_depreciation = self.purchase_price / self.depreciation_years
            current_value = max(0.0, self.purchase_price - annual_depreciation * years_used)
            return round(current_value, 2)
        except (ValueError, TypeError) as e:
            logging.warning(f"[折旧] 资产 {self.asset_id} 计算失败({e})，返回原价（值不可信）")
            return float(self.purchase_price)

    @property
    def depreciation_reliable(self) -> bool:
        """折旧值是否可信：日期/价格/折旧年限齐备且日期格式可解析才为真。
        仅查齐备不算可信——格式错（如 2024/01/01）会在计算时退化为原价，必须显式标记不可信。
        """
        if not (self.purchase_date and self.purchase_price and self.depreciation_years):
            return False
        try:
            datetime.strptime(self.purchase_date, "%Y-%m-%d")
            return True
        except (ValueError, TypeError):
            return False

    @property
    def remaining_warranty_days(self) -> int:
        """剩余质保天数"""
        if not self.warranty_expire:
            return -1
        try:
            expire = datetime.strptime(self.warranty_expire, "%Y-%m-%d")
            remaining = (expire.date() - date.today()).days
            return remaining
        except:
            return -1

    def add_status_history(self, old_status: str, new_status: str, operator: str, remarks: str = ""):
        """记录状态变更"""
        record = {
            "timestamp": datetime.now().isoformat(),
            "from_status": old_status,
            "to_status": new_status,
            "operator": operator,
            "remarks": remarks,
        }
        if self.status_history is None:
            self.status_history = []
        self.status_history.append(record)


# ============ 数据库操作层 ============
def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """初始化数据库表结构（幂等操作）"""
    conn = _get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id TEXT UNIQUE NOT NULL,
            barcode TEXT,
            name TEXT NOT NULL,
            asset_type TEXT,
            brand TEXT,
            model TEXT,
            serial_number TEXT,
            status TEXT DEFAULT 'in_stock',
            status_history TEXT DEFAULT '[]',
            assignee TEXT,
            department TEXT,
            seat_number TEXT,
            location TEXT,
            purchase_date TEXT,
            purchase_price REAL DEFAULT 0,
            supplier TEXT,
            warranty_expire TEXT,
            depreciation_years INTEGER DEFAULT 3,
            mac_address TEXT,
            ip_address TEXT,
            os_version TEXT,
            software_list TEXT DEFAULT '[]',
            created_at TEXT,
            updated_at TEXT,
            operator TEXT,
            remarks TEXT,
            _checksum TEXT
        )
    """)
    # 操作日志表（包含完整审计字段）
    conn.execute("""
        CREATE TABLE IF NOT EXISTS operation_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            asset_id TEXT,
            operation TEXT NOT NULL,
            operator TEXT,
            details TEXT,
            old_value TEXT,
            new_value TEXT,
            session_id TEXT,
            old_snapshot TEXT,
            new_snapshot TEXT
        )
    """)
    # 索引
    conn.execute("CREATE INDEX IF NOT EXISTS idx_asset_id ON assets(asset_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_assignee ON assets(assignee)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_department ON assets(department)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON assets(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_asset_type ON assets(asset_type)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_log_timestamp ON operation_log(timestamp)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_log_operation ON operation_log(operation)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_log_asset ON operation_log(asset_id)")
    # 兼容已有数据库：补全新字段
    _migrate_log_table(conn)
    conn.commit()
    conn.close()
    print(f"[资产系统] 数据库初始化完成: {DB_PATH}")


# ============ JSON双写同步 ============
def _sync_json():
    """将SQLite数据同步到JSON文件（可迁移性保障）"""
    conn = _get_db()
    rows = conn.execute("SELECT * FROM assets").fetchall()
    conn.close()

    assets_list = []
    for row in rows:
        d = dict(row)
        d.pop('id', None)
        d.pop('_checksum', None)
        # JSON兼容处理
        if d.get('status_history'):
            try:
                d['status_history'] = json.loads(d['status_history'])
            except:
                d['status_history'] = []
        if d.get('software_list'):
            try:
                d['software_list'] = json.loads(d['software_list'])
            except:
                d['software_list'] = []
        assets_list.append(d)

    with open(JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump({
            "version": "1.0",
            "exported_at": datetime.now().isoformat(),
            "total_count": len(assets_list),
            "assets": assets_list
        }, f, ensure_ascii=False, indent=2)

    print(f"[资产系统] JSON同步完成: {JSON_PATH} ({len(assets_list)}条记录)")


def _migrate_log_table(conn):
    """迁移已有数据库：补全新增字段（session_id, old_snapshot, new_snapshot）"""
    cursor = conn.execute("PRAGMA table_info(operation_log)")
    existing_cols = [row[1] for row in cursor.fetchall()]
    for col in ['session_id', 'old_snapshot', 'new_snapshot']:
        if col not in existing_cols:
            conn.execute(f"ALTER TABLE operation_log ADD COLUMN {col} TEXT")
            print(f"[资产系统] 审计表新增字段: {col}")


def _log_operation(asset_id: str, operation: str, operator: str,
                   details: str = "", old_value: str = "", new_value: str = "",
                   session_id: str = "",
                   old_snapshot: str = "", new_snapshot: str = ""):
    """记录操作日志（COBIT合规要求）
    Args:
        asset_id: 资产编码
        operation: 操作类型（使用OperationType枚举）
        operator: 操作人
        details: 操作详情说明
        old_value: 旧状态/旧值（简述）
        new_value: 新状态/新值（简述）
        session_id: 批量操作会话ID（用于分组追溯）
        old_snapshot: 操作前资产快照（JSON）
        new_snapshot: 操作后资产快照（JSON）
    """
    conn = _get_db()
    conn.execute(
        """INSERT INTO operation_log
           (timestamp, asset_id, operation, operator, details,
            old_value, new_value, session_id, old_snapshot, new_snapshot)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (datetime.now().isoformat(), asset_id, operation, operator,
         details, old_value, new_value,
         session_id, old_snapshot, new_snapshot)
    )
    conn.commit()
    conn.close()


# ============ 核心CRUD操作 ============
class AssetManager:
    """资产管理系统核心操作类"""

    def __init__(self, operator: str = "系统"):
        self.operator = operator

    # ---- 新增资产 ----
    def add(self, asset: Asset) -> Dict[str, Any]:
        """
        新增资产（入库）
        对应生命周期：→ ①入库
        """
        asset.operator = self.operator
        conn = _get_db()

        try:
            conn.execute("""
                INSERT INTO assets (
                    asset_id, barcode, name, asset_type, brand, model, serial_number,
                    status, status_history, assignee, department, seat_number, location,
                    purchase_date, purchase_price, supplier, warranty_expire, depreciation_years,
                    mac_address, ip_address, os_version, software_list,
                    created_at, updated_at, operator, remarks
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                asset.asset_id, asset.barcode, asset.name, asset.asset_type,
                asset.brand, asset.model, asset.serial_number,
                asset.status, json.dumps(asset.status_history, ensure_ascii=False),
                asset.assignee, asset.department, asset.seat_number, asset.location,
                asset.purchase_date, asset.purchase_price, asset.supplier,
                asset.warranty_expire, asset.depreciation_years,
                asset.mac_address, asset.ip_address, asset.os_version,
                json.dumps(asset.software_list, ensure_ascii=False),
                asset.created_at, asset.updated_at, asset.operator, asset.remarks
            ))
            conn.commit()

            _log_operation(asset.asset_id, OperationType.新增入库, self.operator,
                         f"资产[{asset.name}]入库，系统编码{asset.asset_id}",
                         new_snapshot=json.dumps(asset.to_dict(), ensure_ascii=False, default=str))

            conn.close()
            _sync_json()

            return {
                "success": True,
                "asset_id": asset.asset_id,
                "message": f"资产[{asset.name}]入库成功，编码{asset.asset_id}",
                "asset": asset.to_dict()
            }
        except sqlite3.IntegrityError as e:
            conn.close()
            return {"success": False, "message": f"资产编码已存在：{asset.asset_id}"}
        except Exception as e:
            conn.close()
            return {"success": False, "message": f"入库失败：{str(e)}"}

    # ---- 领用资产 ----
    def assign(self, asset_id: str, assignee: str, department: str, seat_number: str = "", remarks: str = "") -> Dict[str, Any]:
        """
        资产领用
        对应生命周期：①库存 → ②在用
        """
        conn = _get_db()
        cur = conn.execute("SELECT * FROM assets WHERE asset_id = ?", (asset_id,))
        row = cur.fetchone()
        conn.close()

        if not row:
            return {"success": False, "message": f"资产不存在：{asset_id}"}

        asset = _row_to_asset(row)
        old_status = asset.status

        if asset.status not in ["in_stock", "idle"]:
            return {"success": False, "message": f"资产当前状态为[{asset.status}]，无法直接领用"}

        asset.status = "in_use"
        asset.assignee = assignee
        asset.department = department
        asset.seat_number = seat_number
        asset.operator = self.operator
        asset.updated_at = datetime.now().isoformat()
        asset.add_status_history(old_status, "in_use", self.operator, remarks)

        return self._update(asset, old_status, f"领用人：{assignee}（{department}），工位：{seat_number}",
                          operation_type=OperationType.领用)

    # ---- 调拨资产 ----
    def transfer(self, asset_id: str, new_assignee: str, new_department: str,
                 new_seat: str = "", remarks: str = "") -> Dict[str, Any]:
        """
        资产调拨（跨部门/跨工位）
        对应生命周期：②在用 → ③调拨 → ②在用（新归属）
        """
        conn = _get_db()
        cur = conn.execute("SELECT * FROM assets WHERE asset_id = ?", (asset_id,))
        row = cur.fetchone()
        conn.close()

        if not row:
            return {"success": False, "message": f"资产不存在：{asset_id}"}

        asset = _row_to_asset(row)
        old_status = asset.status
        old_assignee = asset.assignee
        old_dept = asset.department

        asset.status = "in_use"
        asset.assignee = new_assignee
        asset.department = new_department
        asset.seat_number = new_seat
        asset.operator = self.operator
        asset.updated_at = datetime.now().isoformat()
        asset.add_status_history(old_status, "in_use", self.operator,
                                 f"调拨：{old_assignee}({old_dept}) → {new_assignee}({new_department})，{remarks}")

        return self._update(asset, old_status,
                          f"从{old_assignee}({old_dept})调拨至{new_assignee}({new_department})",
                          operation_type=OperationType.调拨)

    # ---- 闲置封存 ----
    def idle(self, asset_id: str, remarks: str = "") -> Dict[str, Any]:
        """
        资产闲置封存
        对应生命周期：②在用 → ⑤闲置
        """
        conn = _get_db()
        cur = conn.execute("SELECT * FROM assets WHERE asset_id = ?", (asset_id,))
        row = cur.fetchone()
        conn.close()

        if not row:
            return {"success": False, "message": f"资产不存在：{asset_id}"}

        asset = _row_to_asset(row)
        old_status = asset.status

        if asset.status not in ["in_use", "in_stock"]:
            return {"success": False, "message": f"资产当前状态为[{asset.status}]，无法直接闲置"}

        asset.status = "idle"
        asset.assignee = ""
        asset.seat_number = ""
        asset.operator = self.operator
        asset.updated_at = datetime.now().isoformat()
        asset.add_status_history(old_status, "idle", self.operator, remarks)

        return self._update(asset, old_status, f"闲置封存，备注：{remarks}",
                          operation_type=OperationType.闲置封存)

    # ---- 维保登记 ----
    def repair(self, asset_id: str, remarks: str = "") -> Dict[str, Any]:
        """
        资产进入维保状态
        对应生命周期：②在用 → ④维保
        """
        conn = _get_db()
        cur = conn.execute("SELECT * FROM assets WHERE asset_id = ?", (asset_id,))
        row = cur.fetchone()
        conn.close()

        if not row:
            return {"success": False, "message": f"资产不存在：{asset_id}"}

        asset = _row_to_asset(row)
        old_status = asset.status

        asset.status = "under_repair"
        asset.operator = self.operator
        asset.updated_at = datetime.now().isoformat()
        asset.add_status_history(old_status, "under_repair", self.operator, remarks)

        return self._update(asset, old_status, f"进入维保，备注：{remarks}",
                          operation_type=OperationType.维保登记)

    # ---- 处置/退出 ----
    def dispose(self, asset_id: str, method: str = "scrap", residual_value: float = 0,
                remarks: str = "") -> Dict[str, Any]:
        """
        资产处置/退出
        对应生命周期：任何状态 → ⑥处置
        处置方式：报废/捐赠/二手回收/退租
        """
        conn = _get_db()
        cur = conn.execute("SELECT * FROM assets WHERE asset_id = ?", (asset_id,))
        row = cur.fetchone()
        conn.close()

        if not row:
            return {"success": False, "message": f"资产不存在：{asset_id}"}

        asset = _row_to_asset(row)
        old_status = asset.status

        if asset.status == "disposed":
            return {"success": False, "message": "资产已处置，无法重复操作"}

        disposal_record = {
            "method": method,
            "residual_value": residual_value,
            "remarks": remarks,
            "disposed_at": datetime.now().isoformat(),
            "disposed_by": self.operator,
        }

        asset.status = "disposed"
        asset.assignee = ""
        asset.seat_number = ""
        asset.operator = self.operator
        asset.updated_at = datetime.now().isoformat()
        asset.remarks = f"{asset.remarks}\n[处置记录]{json.dumps(disposal_record, ensure_ascii=False)}" if asset.remarks else f"[处置记录]{json.dumps(disposal_record, ensure_ascii=False)}"
        asset.add_status_history(old_status, "disposed", self.operator,
                                 f"处置方式：{DisposalMethod(method).label}，残余价值：{residual_value}元，备注：{remarks}")

        result = self._update(asset, old_status,
                             f"处置方式：{DisposalMethod(method).label}，残余价值{residual_value}元",
                             operation_type=OperationType.处置)
        result["disposal_record"] = disposal_record
        return result

    # ---- 查询资产 ----
    def get(self, asset_id: str) -> Optional[Dict]:
        """按资产编码查询"""
        conn = _get_db()
        cur = conn.execute("SELECT * FROM assets WHERE asset_id = ?", (asset_id,))
        row = cur.fetchone()
        conn.close()

        if not row:
            return None
        asset = _row_to_asset(row)
        return asset.to_dict()

    def find_by_assignee(self, assignee: str) -> List[Dict]:
        """按使用人查询名下资产"""
        conn = _get_db()
        cur = conn.execute(
            "SELECT * FROM assets WHERE assignee LIKE ? AND status != 'disposed'",
            (f"%{assignee}%",)
        )
        rows = cur.fetchall()
        conn.close()
        return [_row_to_asset(r).to_dict() for r in rows]

    def find_by_department(self, department: str) -> List[Dict]:
        """按部门查询资产"""
        conn = _get_db()
        cur = conn.execute(
            "SELECT * FROM assets WHERE department LIKE ? AND status != 'disposed'",
            (f"%{department}%",)
        )
        rows = cur.fetchall()
        conn.close()
        return [_row_to_asset(r).to_dict() for r in rows]

    def list_by_status(self, status: str) -> List[Dict]:
        """按状态查询资产"""
        conn = _get_db()
        cur = conn.execute("SELECT * FROM assets WHERE status = ?", (status,))
        rows = cur.fetchall()
        conn.close()
        return [_row_to_asset(r).to_dict() for r in rows]

    def list_idle(self) -> List[Dict]:
        """查询所有闲置资产（可重新分配）"""
        return self.list_by_status("idle")

    def list_all(self, include_disposed: bool = False) -> List[Dict]:
        """查询全部资产"""
        conn = _get_db()
        if include_disposed:
            cur = conn.execute("SELECT * FROM assets ORDER BY updated_at DESC")
        else:
            cur = conn.execute("SELECT * FROM assets WHERE status != 'disposed' ORDER BY updated_at DESC")
        rows = cur.fetchall()
        conn.close()
        return [_row_to_asset(r).to_dict() for r in rows]

    def search(self, keyword: str) -> List[Dict]:
        """关键词搜索（名称/编码/SN/使用人）"""
        conn = _get_db()
        kw = f"%{keyword}%"
        cur = conn.execute("""
            SELECT * FROM assets WHERE
            asset_id LIKE ? OR name LIKE ? OR serial_number LIKE ?
            OR assignee LIKE ? OR brand LIKE ? OR model LIKE ?
            ORDER BY updated_at DESC
        """, (kw, kw, kw, kw, kw, kw))
        rows = cur.fetchall()
        conn.close()
        return [_row_to_asset(r).to_dict() for r in rows]

    def count(self, status: Optional[str] = None) -> int:
        """统计资产数量"""
        conn = _get_db()
        if status:
            cur = conn.execute("SELECT COUNT(*) FROM assets WHERE status = ?", (status,))
        else:
            cur = conn.execute("SELECT COUNT(*) FROM assets")
        count = cur.fetchone()[0]
        conn.close()
        return count

    def summary(self) -> Dict[str, Any]:
        """资产统计摘要"""
        conn = _get_db()
        cur = conn.execute("""
            SELECT status, COUNT(*) as count,
                   SUM(CASE WHEN purchase_price > 0 THEN purchase_price ELSE 0 END) as total_value
            FROM assets GROUP BY status
        """)
        rows = cur.fetchall()
        conn.close()

        status_map = {}
        total_count = 0
        total_value = 0.0
        for row in rows:
            status_map[row['status']] = {"count": row['count'], "value": row['total_value'] or 0}
            total_count += row['count']
            total_value += row['total_value'] or 0

        return {
            "total_count": total_count,
            "total_value": round(total_value, 2),
            "by_status": status_map,
            "in_use_count": status_map.get("in_use", {}).get("count", 0),
            "idle_count": status_map.get("idle", {}).get("count", 0),
            "disposed_count": status_map.get("disposed", {}).get("count", 0),
        }

    # ---- 批量导入 ----
    def import_batch(self, assets_data: List[Dict]) -> Dict[str, Any]:
        """
        批量导入资产数据（从Excel清洗后的底账导入）
        跳过已存在的编码
        """
        success_count = 0
        skip_count = 0
        errors = []

        for data in assets_data:
            try:
                asset = Asset(
                    asset_id=data.get("asset_id", ""),
                    barcode=data.get("barcode", ""),
                    name=data.get("name", ""),
                    asset_type=data.get("asset_type", "other"),
                    brand=data.get("brand", ""),
                    model=data.get("model", ""),
                    serial_number=data.get("serial_number", ""),
                    status=data.get("status", "in_stock"),
                    assignee=data.get("assignee", ""),
                    department=data.get("department", ""),
                    seat_number=data.get("seat_number", ""),
                    location=data.get("location", ""),
                    purchase_date=data.get("purchase_date", ""),
                    purchase_price=data.get("purchase_price", 0.0),
                    supplier=data.get("supplier", ""),
                    warranty_expire=data.get("warranty_expire", ""),
                    mac_address=data.get("mac_address", ""),
                    remarks=data.get("remarks", ""),
                )
                result = self.add(asset)
                if result["success"]:
                    success_count += 1
                else:
                    skip_count += 1
            except Exception as e:
                errors.append(f"{data.get('name','未知')}：{str(e)}")

        _sync_json()
        return {
            "success": True,
            "imported": success_count,
            "skipped": skip_count,
            "errors": errors[:10],  # 最多显示10条错误
            "message": f"导入完成：新增{success_count}条，跳过{skip_count}条"
        }

    # ---- 内部更新方法 ----
    def _update(self, asset: Asset, old_status: str, details: str,
                operation_type: str = None) -> Dict[str, Any]:
        """内部更新方法，带审计快照
        Args:
            asset: 更新后的资产对象
            old_status: 更新前的状态
            details: 操作详情
            operation_type: 操作类型（使用OperationType枚举），默认"状态变更"
        """
        if operation_type is None:
            operation_type = OperationType.状态变更

        # 捕获操作前的快照（从DB读取最新数据）
        conn = _get_db()
        old_row = conn.execute(
            "SELECT * FROM assets WHERE asset_id = ?", (asset.asset_id,)
        ).fetchone()
        old_snapshot = ""
        if old_row:
            old_dict = dict(old_row)
            old_dict.pop('id', None)
            old_dict.pop('_checksum', None)
            old_snapshot = json.dumps(old_dict, ensure_ascii=False, default=str)

        # 执行更新
        conn.execute("""
            UPDATE assets SET
                barcode=?, name=?, asset_type=?, brand=?, model=?, serial_number=?,
                status=?, status_history=?, assignee=?, department=?, seat_number=?, location=?,
                purchase_date=?, purchase_price=?, supplier=?, warranty_expire=?, depreciation_years=?,
                mac_address=?, ip_address=?, os_version=?, software_list=?,
                updated_at=?, operator=?, remarks=?
            WHERE asset_id=?
        """, (
            asset.barcode, asset.name, asset.asset_type, asset.brand, asset.model, asset.serial_number,
            asset.status, json.dumps(asset.status_history, ensure_ascii=False),
            asset.assignee, asset.department, asset.seat_number, asset.location,
            asset.purchase_date, asset.purchase_price, asset.supplier, asset.warranty_expire, asset.depreciation_years,
            asset.mac_address, asset.ip_address, asset.os_version, json.dumps(asset.software_list, ensure_ascii=False),
            asset.updated_at, asset.operator, asset.remarks,
            asset.asset_id
        ))
        conn.commit()

        # 捕获操作后的快照
        new_dict = {
            "asset_id": asset.asset_id, "name": asset.name, "status": asset.status,
            "assignee": asset.assignee, "department": asset.department,
            "seat_number": asset.seat_number, "location": asset.location,
            "updated_at": asset.updated_at, "operator": asset.operator,
        }
        new_snapshot = json.dumps(new_dict, ensure_ascii=False, default=str)

        conn.close()
        _sync_json()

        # 写入审计日志（带快照）
        _log_operation(
            asset.asset_id, operation_type, self.operator,
            details, old_status, asset.status,
            old_snapshot=old_snapshot, new_snapshot=new_snapshot
        )

        return {
            "success": True,
            "asset_id": asset.asset_id,
            "message": f"资产[{asset.name}]状态更新：{AssetStatus(old_status).label} → {AssetStatus(asset.status).label}",
            "details": details,
            "operation_type": operation_type,
            "asset": asset.to_dict()
        }

    # ---- 彻底删除资产（带审计记录）----
    def delete(self, asset_id: str, reason: str = "") -> Dict[str, Any]:
        """
        从数据库和JSON中彻底删除资产记录（不可恢复）
        仅用于数据清理场景（如台账中不存在的误录入资产）
        审计要求：删除前先写入"彻底删除"审计日志
        """
        conn = _get_db()
        cur = conn.execute("SELECT * FROM assets WHERE asset_id = ?", (asset_id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            return {"success": False, "message": f"资产不存在：{asset_id}"}

        asset_info = dict(row)
        # 先写审计日志（必须在删除资产记录之前写入）
        asset_snapshot = json.dumps(
            {k: v for k, v in asset_info.items()
             if k not in ('id', '_checksum')},
            ensure_ascii=False, default=str
        )
        _log_operation(
            asset_id, OperationType.彻底删除, self.operator,
            details=f"彻底删除，原因：{reason if reason else '用户主动删除'}",
            old_value=asset_info.get('status', ''),
            new_value="deleted",
            old_snapshot=asset_snapshot
        )
        # 再执行删除（包括清理该资产的旧操作记录）
        conn.execute("DELETE FROM assets WHERE asset_id = ?", (asset_id,))
        conn.execute("DELETE FROM operation_log WHERE asset_id = ? AND operation != ?",
                     (asset_id, OperationType.彻底删除))
        conn.commit()
        conn.close()
        _sync_json()

        return {
            "success": True,
            "asset_id": asset_id,
            "message": f"资产[{asset_info.get('name','')}]已彻底删除。原因：{reason if reason else '用户主动删除'}",
            "deleted_asset": asset_info.get('name', ''),
            "deleted_status": asset_info.get('status', ''),
        }


# ============ 辅助函数 ============
def _row_to_asset(row: sqlite3.Row) -> Asset:
    """SQLite Row对象转Asset对象"""
    d = dict(row)
    d.pop('id', None)
    d.pop('_checksum', None)
    if d.get('status_history'):
        try:
            d['status_history'] = json.loads(d['status_history'])
        except:
            d['status_history'] = []
    if d.get('software_list'):
        try:
            d['software_list'] = json.loads(d['software_list'])
        except:
            d['software_list'] = []
    return Asset(**{k: v for k, v in d.items() if k in Asset.__dataclass_fields__})


def get_operation_log(asset_id: Optional[str] = None, limit: int = 50,
                      operation_type: Optional[str] = None,
                      start_date: Optional[str] = None,
                      end_date: Optional[str] = None) -> List[Dict]:
    """查询操作日志（支持多维度筛选）
    Args:
        asset_id: 按资产编码筛选
        limit: 返回条数上限
        operation_type: 按操作类型筛选
        start_date: 起始日期（ISO格式，如"2026-05-01"）
        end_date: 截止日期（ISO格式，如"2026-05-21"）
    """
    conn = _get_db()
    conditions = []
    params = []

    if asset_id:
        conditions.append("asset_id = ?")
        params.append(asset_id)
    if operation_type:
        conditions.append("operation = ?")
        params.append(operation_type)
    if start_date:
        conditions.append("timestamp >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("timestamp <= ?")
        params.append(end_date + "T23:59:59")

    where_clause = " AND ".join(conditions) if conditions else "1=1"
    cur = conn.execute(
        f"SELECT * FROM operation_log WHERE {where_clause} ORDER BY timestamp DESC LIMIT ?",
        params + [limit]
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_audit_summary() -> Dict[str, Any]:
    """审计摘要：各操作类型统计 + 操作人统计"""
    conn = _get_db()
    # 按操作类型统计
    op_counts = {}
    cur = conn.execute(
        "SELECT operation, COUNT(*) as cnt FROM operation_log GROUP BY operation ORDER BY cnt DESC"
    )
    for row in cur.fetchall():
        op_counts[row['operation']] = row['cnt']
    # 按操作人统计
    op_by_user = {}
    cur = conn.execute(
        "SELECT operator, COUNT(*) as cnt FROM operation_log GROUP BY operator ORDER BY cnt DESC"
    )
    for row in cur.fetchall():
        op_by_user[row['operator']] = row['cnt']
    # 时间范围
    cur = conn.execute("SELECT MIN(timestamp) as first, MAX(timestamp) as last FROM operation_log")
    row = cur.fetchone()
    conn.close()

    return {
        "total_entries": sum(op_counts.values()),
        "time_range": {"first": row['first'] if row else '', "last": row['last'] if row else ''},
        "by_operation_type": op_counts,
        "by_operator": op_by_user,
    }


def export_json() -> str:
    """导出JSON（外部调用）"""
    _sync_json()
    return JSON_PATH


# ============ 启动初始化 ============
if __name__ == "__main__":
    init_db()
    print(f"[资产系统] 初始化完成，数据库: {DB_PATH}")
    print(f"[资产系统] 当前资产数量: {AssetManager().count()}")
    print(f"[资产系统] 统计摘要: {AssetManager().summary()}")
