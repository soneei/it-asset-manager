-- IT 资产管理系统 — 数据库表结构（仅结构，无数据）
-- 用法: sqlite3 data/assets.db < schema/schema.sql

-- 表: assets
CREATE TABLE assets (
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
        , order_number TEXT, disk TEXT, memory TEXT, cpu TEXT, oa_payment_number TEXT, assign_date TEXT);

-- 表: operation_log
CREATE TABLE operation_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            asset_id TEXT,
            operation TEXT NOT NULL,
            operator TEXT,
            details TEXT,
            old_value TEXT,
            new_value TEXT
        , session_id TEXT, old_snapshot TEXT, new_snapshot TEXT);

