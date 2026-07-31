# IT 资产管理系统（开源版）

一套**通用的** IT 资产管理与二维码标签系统。本仓库**仅包含系统代码**，**不含任何真实资产数据、员工信息或公司信息**——所有数据由使用者自行导入，完全自控。

> 设计原则：**系统是系统，数据是数据**。本系统是一个空引擎，运行时才从你自己的数据库读取数据；你导入什么，它就展示什么。

## 功能特性

- 📊 **资产大盘**：Web 界面浏览、检索、筛选资产
- 📱 **扫码详情**：手机扫码（二维码）→ 实时查库返回资产详情页
- 🏷️ **标签打印**：生成精臣 B50（50×30mm）二维码标签，可批量打印
- 📥 **Excel 导入**：按 `sample_data/导入模板.xlsx` 列头填入你自己的台账即可导入
- 🔒 **数据自控**：本地 SQLite，不上云、不依赖任何外部服务

## 快速开始

```bash
# 1. 安装依赖
pip install fastapi uvicorn openpyxl qrcode pillow

# 2. 初始化空数据库（仅表结构，零数据）
sqlite3 data/assets.db < schema/schema.sql

# 3. 用 sample_data/导入模板.xlsx 填好你自己的资产，另存为 input.xlsx
#    然后执行导入（生成 data/assets.json 供标签/详情页使用）
python3 convert_excel.py

# 4. 生成标签（二维码地址通过环境变量注入，不写死）
export ASSET_LABEL_BASE_URL="http://你的服务器IP:8088/api/scan/"
python3 gen_labels.py

# 5. 启动 Web 服务
python3 web_server.py
# 浏览器打开 http://localhost:8088
```

## 二维码地址说明

标签二维码只编码一个 URL 前缀（如 `http://你的服务器:8088/api/scan/`），扫码时由你的服务实时查库返回详情。
- 内网部署：手机需连接同一 WiFi/VPN 才能扫开（数据不出局域网）。
- 公网部署：将系统托管到你自己的已备案域名/云服务器即可随处可扫。
- `gen_labels.py` 通过环境变量 `ASSET_LABEL_BASE_URL` 切换地址，代码内**不硬编码任何具体地址**。

## 目录结构

```
opensource-clean/
├── web_server.py            # Web 服务（大盘/扫码/标签/导出）
├── gen_labels.py            # 标签生成（二维码地址走环境变量）
├── gen_asset_detail.py      # 详情页生成
├── asset_manager.py         # 资产管理核心引擎
├── asset_cli.py             # 命令行交互接口
├── convert_excel.py        # Excel → 数据库 导入
├── migrate_asset_data.py   # 数据迁移校准
├── import_from_desktop.py  # 桌面端台账导入
├── enrich_db.py / force_import.py / force_populate.py / recover_hardware_info.py / alter_db.py
├── check_*.py / test_*.py / verify_import.py / missing_ids.py / investigate_excel.py  # 校验与测试
├── templates/              # 数据驱动模板（不含数据）
│   ├── index.html          # 资产大盘
│   ├── scan.html           # 扫码详情页
│   ├── asset_detail_page.html
│   ├── print_label.html    # 标签打印
│   └── dashboard_script.html
├── schema/
│   └── schema.sql          # 仅表结构（零数据）
├── sample_data/
│   └── 导入模板.xlsx        # 空白导入模板（列头对齐）
├── data/                   # 你自己的数据库放这里（.gitignore 已排除）
└── .gitignore
```

## 安全声明

本仓库的所有代码与文档**均不含任何真实公司、员工或资产数据**。文档与代码中的示例名称（如 `EXAMPLE-001`、`DEMO-ASSET-0001`）均为占位符。
请**不要**在 Issue / PR 中提交任何真实资产数据。

## License

MIT —— 见 [LICENSE](./LICENSE)。
