#!/usr/bin/env python3
"""从assets.db全量生成asset_detail.html（内嵌所有资产数据）"""
import sqlite3
import json
import os
from datetime import datetime

DB_PATH = "os.path.join(os.path.dirname(__file__), 'data', 'assets.db')"
OUTPUT_PATH = "os.path.join(os.path.dirname(__file__), 'data', 'asset_detail.html')"

status_zh = {"in_use": "在用", "in_stock": "闲置入库", "scrapped": "已报废", "disposed": "已处置"}
type_map_zh = {
    'laptop': '笔记本', 'desktop': '台式机', 'monitor': '显示器',
    'phone': '手机', 'tablet': '平板', 'keyboard_mouse': '键鼠',
    'printer': '打印机', 'other': '其他'
}

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
rows = conn.execute("SELECT * FROM assets").fetchall()
print(f"从DB读取 {len(rows)} 条资产记录")

assets = []
for r in rows:
    d = dict(r)
    price = d.get('purchase_price')
    price_str = f"¥{price:,.2f}" if price and price > 0 else "-"
    
    a = {
        "id": d.get('asset_id', ''),
        "name": d.get('name', ''),
        "type": type_map_zh.get(d.get('asset_type', ''), d.get('asset_type', '')),
        "brand": d.get('brand', '') or '',
        "model": d.get('model', '') or '',
        "sn": d.get('serial_number', '') or '-',
        "status": d.get('status', ''),
        "status_label": status_zh.get(d.get('status', ''), d.get('status', '')),
        "assignee": d.get('assignee', '') or '-',
        "dept": d.get('department', '') or '-',
        "location": d.get('location', '') or '-',
        "purchase_date": d.get('purchase_date', '') or '-',
        "price": price_str,
        "supplier": d.get('supplier', '') or '-',
        "warranty": d.get('warranty_expire', '') or '-',
        "oa_no": d.get('oa_payment_number', '') or '-',
        "remarks": d.get('remarks', '') or '-',
        "mac": d.get('mac_address', '') or '-',
    }
    assets.append(a)

conn.close()

# HTML模板（保持原有样式和交互逻辑）
html_template = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<!-- ℹ️ 静态资产详情页 — 由脚本自动生成，内嵌全量数据 -->
<!-- 生成时间: {generated_time} | 资产总数: {total_count} -->
<!-- 数据来源: assets.db (SQLite) — 每次资产变更后需重新生成并部署 -->
<title>IT 资产管理系统资产查询</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;background:#f5f6fa;color:#2d3436;min-height:100vh}}
.detail-hero{{background:linear-gradient(135deg,#6c5ce7,#a29bfe);color:#fff;padding:32px 24px 40px}}
.detail-hero .code{{font-family:'SF Mono',monospace;font-size:16px;opacity:.9;margin-bottom:4px}}
.detail-hero h1{{font-size:24px;font-weight:700;margin-bottom:6px}}
.detail-hero .sub{{font-size:14px;opacity:.8}}
.detail-hero .status-badge{{display:inline-block;margin-top:12px;padding:4px 16px;border-radius:20px;background:rgba(255,255,255,.2);font-size:13px;font-weight:500}}
.detail-section{{background:#fff;margin:16px;border-radius:12px;padding:20px;box-shadow:0 2px 8px rgba(0,0,0,.06)}}
.detail-section h3{{font-size:14px;color:#636e72;margin-bottom:12px;padding-bottom:8px;border-bottom:1px solid #f1f2f6}}
.detail-grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
.detail-item{{}}
.detail-item .l{{font-size:12px;color:#b2bec3;margin-bottom:2px}}
.detail-item .v{{font-size:15px;font-weight:500;color:#2d3436}}
.detail-item.full{{grid-column:1/-1}}
.detail-footer{{text-align:center;padding:20px;color:#b2bec3;font-size:12px}}
.error-page{{text-align:center;padding:80px 20px;color:#b2bec3;font-size:14px;line-height:2}}
.error-page .icon{{font-size:48px;margin-bottom:16px}}
</style>
</head>
<body>
<div id="app"></div>
<script>
const ASSETS = {assets_json};
(function(){{
const params = new URLSearchParams(window.location.search);
const aid = params.get('aid');
if(aid){{
    const a = ASSETS.find(x => x.id.toLowerCase() === aid.toLowerCase());
    if(a){{
        showDetail(a);
    }}else{{
        document.getElementById('app').innerHTML = '<div class="error-page"><div class="icon">🔍</div>未找到该资产信息<br>请确认二维码是否有效</div>';
    }}
}}else{{
    document.getElementById('app').innerHTML = '<div class="error-page"><div class="icon">📱</div>请扫描资产二维码查看设备信息</div>';
}}

function showDetail(a){{
    document.getElementById('app').innerHTML = `
    <div class="detail-page">
        <div class="detail-hero">
            <div class="code">${{a.id}}</div>
            <h1>${{a.name}}</h1>
            <div class="sub">${{a.assignee}} · ${{a.dept}}</div>
            <div class="status-badge">${{a.status_label}}</div>
        </div>
        <div class="detail-section">
            <h3>设备信息</h3>
            <div class="detail-grid">
                <div class="detail-item"><div class="l">类型</div><div class="v">${{a.type}}</div></div>
                <div class="detail-item"><div class="l">品牌</div><div class="v">${{a.brand}}</div></div>
                <div class="detail-item full"><div class="l">型号</div><div class="v">${{a.model}}</div></div>
                <div class="detail-item full"><div class="l">序列号</div><div class="v">${{a.sn}}</div></div>
                <div class="detail-item"><div class="l">所在地</div><div class="v">${{a.location}}</div></div>
                <div class="detail-item"><div class="l">MAC地址</div><div class="v">${{a.mac}}</div></div>
            </div>
            <div style="margin-top: 12px;">
                <span style="display:inline-block;background:#6c5ce7;color:#fff;padding:8px 16px;border-radius:20px;font-size:13px;font-weight:600;">📋 扫码查看实时状态</span>
            </div>
        </div>
        <div class="detail-section">
            <h3>采购信息</h3>
            <div class="detail-grid">
                <div class="detail-item"><div class="l">采购日期</div><div class="v">${{a.purchase_date}}</div></div>
                <div class="detail-item"><div class="l">采购价格</div><div class="v">${{a.price}}</div></div>
                <div class="detail-item"><div class="l">供应商</div><div class="v">${{a.supplier}}</div></div>
                <div class="detail-item"><div class="l">维保到期</div><div class="v">${{a.warranty}}</div></div>
                <div class="detail-item"><div class="l">OA付款单号</div><div class="v">${{a.oa_no}}</div></div>
            </div>
        </div>
        <div class="detail-section">
            <h3>备注</h3>
            <div style="font-size:14px;color:#636e72;line-height:1.6">${{a.remarks}}</div>
        </div>
        <div class="detail-footer">IT 资产管理系统资产管理 · 数据更新于 {generated_time}</div>
    </div>`;
}}
}})();
</script>
</body>
</html>'''

assets_json = json.dumps(assets, ensure_ascii=False)
output = html_template.format(
    generated_time=datetime.now().strftime("%Y-%m-%d %H:%M"),
    total_count=len(assets),
    assets_json=assets_json
)

with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
    f.write(output)

size_kb = len(output.encode('utf-8')) / 1024
print(f"✅ 已生成: {OUTPUT_PATH}")
print(f"   资产数: {len(assets)}")
print(f"   文件大小: {size_kb:.1f} KB")
