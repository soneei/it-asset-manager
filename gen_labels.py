#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成精臣B50(50x30mm)资产标签，标签本体只含稳定字段：品牌 / 资产编码 / 名称 / 配置·SN / 二维码。
严禁写入使用人、部门、采购日期、价格等易变字段（资产审计铁律）。

输出：
  1) 标签批量打印[_后缀].html  —— 全量资产批量打印（github.io版默认名，内网版带"内网版"后缀）
  2) 标签[_后缀]ASSET-*.html   —— 已有单独标签文件按新地址重生成

★ 二维码地址通过环境变量切换（不写死）：
  ASSET_LABEL_BASE_URL  二维码URL前缀（自动拼资产编码），默认 GitHub Pages 固定地址
  ASSET_LABEL_OUT_SUFFIX 输出文件后缀，默认空（github.io版）；内网版用 "内网版"

⚠️ 重要：github.io 在中国大陆手机侧普遍不可达（被墙/DNS污染），已证伪不可用；
   内网实时查库地址（如 http://内网地址:端口/api/scan/）仅办公室WiFi可扫；
   真正"随处可扫(含蜂窝)"需国内云托管(腾讯云/阿里云+备案域名)。
"""
import sqlite3
import os
import shutil
from datetime import datetime

DB = "os.path.join(os.path.dirname(__file__), 'data', 'assets.db')"
LABELDIR = "os.path.join(os.path.dirname(__file__), '标签')"

# ★ 二维码目标地址前缀（烤进标签的 URL 前缀，自动拼资产编码）★
# 默认 GitHub Pages 固定地址；可用环境变量 ASSET_LABEL_BASE_URL 覆盖（如内网实时查库地址）。
# ⚠️ github.io 在中国大陆手机侧普遍不可达，已证伪；内网/国内云托管地址请用环境变量注入。
BASE_URL = os.environ.get(
    "ASSET_LABEL_BASE_URL",
    "https://YOUR_USERNAME.github.io/YOUR_REPO/asset-labels/asset_detail.html?aid="
)

CARD_CSS = """
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:"PingFang SC","Microsoft YaHei",sans-serif; background:#f0f0f0; padding:10px; }
.page { display:flex; flex-wrap:wrap; gap:8px; justify-content:center; }
.label-card { width:590px; height:354px; background:#fff; border-radius:8px;
  box-shadow:0 2px 8px rgba(0,0,0,.1); position:relative; overflow:hidden;
  padding:20px 24px; display:flex; align-items:center; }
.left { flex:1; min-width:0; }
.right { flex-shrink:0; margin-left:16px; text-align:center; }
.tag-brand { display:inline-block; background:#6c5ce7; color:#fff; padding:4px 14px;
  border-radius:20px; font-size:12px; font-weight:600; letter-spacing:1px; margin-bottom:10px; }
.asset-code { font-size:22px; font-weight:700; color:#2d3436; margin-bottom:6px;
  letter-spacing:1px; font-family:"SF Mono",monospace; }
.asset-name { font-size:20px; font-weight:600; color:#6c5ce7; margin-bottom:4px;
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.asset-info { font-size:13px; color:#636e72; line-height:1.7; }
.live-tip { margin-top:10px; font-size:12px; color:#00b894; font-weight:500; }
.qr-wrap { width:140px; height:140px; }
.qr-wrap img, .qr-wrap canvas { width:100%!important; height:100%!important; }
.qr-tip { font-size:11px; color:#6c5ce7; margin-top:4px; }
@media print {
  body { background:#fff; padding:0; }
  .label-card { box-shadow:none; border-radius:0; page-break-after:always; break-inside:avoid; }
  .page { gap:0; }
}
"""


def label_card(a):
    aid = a["asset_id"]
    name = a["name"] or "-"
    brand = a["brand"] or ""
    model = a["model"] or ""
    brand_model = (brand + " · " + model).strip(" ·") if (brand or model) else "-"
    parts = []
    if a["cpu"]:
        parts.append(str(a["cpu"]))
    if a["memory"]:
        parts.append(str(a["memory"]))
    if a["disk"]:
        parts.append(str(a["disk"]))
    config = " · ".join(parts) if parts else "-"
    sn = a["serial_number"] or "待补"
    url = f"{BASE_URL}{aid}"
    return f'''  <div class="label-card">
    <div class="left">
      <div class="tag-brand">IT 资产管理系统资产</div>
      <div class="asset-code">{aid}</div>
      <div class="asset-name">{name}</div>
      <div class="asset-info">{brand_model}<br>{config} · SN:{sn}</div>
      <div class="live-tip">📱 扫码查看实时状态</div>
    </div>
    <div class="right">
      <div class="qr-wrap" data-url="{url}"></div>
      <div class="qr-tip">扫码查看详情</div>
    </div>
  </div>'''


def main():
    OUT_SUFFIX = os.environ.get("ASSET_LABEL_OUT_SUFFIX", "")
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT asset_id,name,brand,model,cpu,memory,disk,serial_number,status "
        "FROM assets ORDER BY asset_id"
    ).fetchall()
    conn.close()
    print(f"从DB读取 {len(rows)} 条资产")

    cards = "\n".join(label_card(dict(r)) for r in rows)

    bulk = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>IT 资产管理系统资产标签批量打印 - 精臣B50 50×30mm</title>
<!-- 固定公网地址(GitHub Pages，永久不变): {BASE_URL} -->
<style>{CARD_CSS}</style>
</head>
<body>
<div class="page">
{cards}
</div>
<script src="https://cdn.jsdelivr.net/npm/qrcodejs@1.0.0/qrcode.min.js"></script>
<script>
document.querySelectorAll('.qr-wrap[data-url]').forEach(function(el){{
  new QRCode(el, {{
    text: el.getAttribute('data-url'),
    width: 140, height: 140,
    colorDark: "#2d3436", colorLight: "#ffffff",
    correctLevel: QRCode.CorrectLevel.M
  }});
}});
</script>
</body>
</html>'''

    # 批量文件名（支持内网版等后缀，避免覆盖 github.io 版）
    if OUT_SUFFIX:
        bulk_name = f"标签批量打印_{OUT_SUFFIX}.html"
    else:
        bulk_name = "标签批量打印_精臣B50.html"
    # 备份并覆盖旧批量文件
    old = os.path.join(LABELDIR, bulk_name)
    if os.path.exists(old):
        shutil.copy2(old, old + f".bak_{datetime.now():%Y%m%d}")
        print(f"已备份旧批量文件 -> {old}.bak_{datetime.now():%Y%m%d}")
    bulk_path = old
    with open(bulk_path, "w", encoding="utf-8") as f:
        f.write(bulk)
    print(f"✅ 批量标签已生成: {bulk_path}  ({len(rows)} 个标签)")

    # 重生成已有的单独标签文件
    single_tpl = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>IT 资产管理系统资产标签 - {aid}</title>
<style>{CSS}</style>
</head>
<body>
<div class="page">
{card}
</div>
<script src="https://cdn.jsdelivr.net/npm/qrcodejs@1.0.0/qrcode.min.js"></script>
<script>
document.querySelectorAll('.qr-wrap[data-url]').forEach(function(el){{
  new QRCode(el, {{
    text: el.getAttribute('data-url'),
    width: 140, height: 140,
    colorDark: "#2d3436", colorLight: "#ffffff",
    correctLevel: QRCode.CorrectLevel.M
  }});
}});
</script>
</body>
</html>'''

    regen = 0
    for r in rows:
        a = dict(r)
        aid = a["asset_id"]
        fpath = os.path.join(LABELDIR, f"标签_{OUT_SUFFIX}{aid}.html")
        if os.path.exists(fpath):
            html = single_tpl.replace("{CSS}", CARD_CSS).replace("{aid}", aid).replace("{card}", label_card(a))
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(html)
            regen += 1
    print(f"✅ 已按固定地址重生成 {regen} 个单独标签文件")

    print(f"\n标签二维码地址前缀: {BASE_URL}  (自动拼接资产编码)")
    print("提示: 资产信息变更后，重跑本脚本即可刷新全部标签内容（地址不变，无需重打）。")


if __name__ == "__main__":
    main()
