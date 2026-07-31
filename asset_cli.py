"""
IT 资产管理系统资产管理系统 — 对话式交互接口
用于WorkBuddy自然语言调用

使用方式（WorkBuddy中直接说）：
  "入库一台MacBook Pro给小王"       → add
  "小王有几台设备"                   → find_by_assignee
  "查一下MY-2026-0001"              → get
  "把MY-2026-0001调给小李"          → transfer
  "MY-2026-0001闲置了"              → idle
  "MY-2026-0001处置了"              → dispose
  "资产统计"                         → summary
  "搜索苹果"                         → search
  "查一下在用资产"                   → list_by_status
  "查一下闲置资产"                   → list_idle
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from asset_manager import (
    AssetManager, Asset, AssetStatus, AssetType, DisposalMethod,
    init_db, export_json, get_operation_log
)
from typing import List
import json


# ============ 对话式命令解析 ============

def parse_command(text: str, operator: str = "WorkBuddy") -> dict:
    """
    解析自然语言命令，返回执行结果
    返回格式：{"success": bool, "reply": str, "data": ...}
    """
    text = text.strip()
    mgr = AssetManager(operator)

    # === 查询类命令 ===
    if "资产统计" in text or ("有多少" and "资产" in text):
        summary = mgr.summary()
        total = summary["total_count"]
        in_use = summary.get("in_use_count", 0)
        idle = summary.get("idle_count", 0)
        disposed = summary.get("disposed_count", 0)
        total_value = summary.get("total_value", 0)
        lines = [
            f"📊 资产统计摘要",
            f"总资产数量：{total} 台",
            f"在用：{in_use} 台",
            f"闲置：{idle} 台",
            f"已处置：{disposed} 台",
            f"总采购价值：¥{total_value:,.2f}",
        ]
        if summary.get("by_status"):
            for st, info in summary["by_status"].items():
                label = AssetStatus(st).label if st in [e.value for e in AssetStatus] else st
                lines.append(f"  {label}：{info['count']}台（价值¥{info['value']:,.2f}）")
        return {"success": True, "reply": "\n".join(lines), "data": summary}

    if "查一下" in text or "看看" in text or "搜索" in text:
        # 提取关键词
        keyword = text.replace("查一下", "").replace("看看", "").replace("搜索", "").strip()
        if not keyword:
            return {"success": False, "reply": "请告诉我你要查什么？比如：查一下小王的资产"}
        results = mgr.search(keyword)
        if not results:
            return {"success": True, "reply": f"没有找到包含「{keyword}」的资产"}
        return format_list(results, f"搜索「{keyword}」找到 {len(results)} 条结果")

    if "闲置资产" in text or "空闲设备" in text:
        results = mgr.list_idle()
        if not results:
            return {"success": True, "reply": "暂无闲置资产"}
        return format_list(results, f"闲置资产 {len(results)} 台，可重新分配")

    if "在用资产" in text:
        results = mgr.list_by_status("in_use")
        return format_list(results, f"在用资产 {len(results)} 台")

    if "库存" in text:
        results = mgr.list_by_status("in_stock")
        return format_list(results, f"库存资产 {len(results)} 台")

    # === 按人员查询 ===
    for kw in ["有几台", "有什么", "名下", "查他的"]:
        if kw in text:
            # 提取人名
            parts = text.replace("有几台", "").replace("有什么", "").replace("名下", "").replace("查他的", "").replace("查一下", "")
            parts = parts.replace("的资产", "").replace("设备", "").replace("电脑", "").strip()
            results = mgr.find_by_assignee(parts)
            if not results:
                return {"success": True, "reply": f"没有找到「{parts}」名下的资产"}
            return format_list(results, f"「{parts}」名下有 {len(results)} 台资产")

    # === 按编码精确查询 ===
    import re
    code_match = re.search(r"MY-\d{4}-\d{4}", text)
    if code_match:
        code = code_match.group(0)
        asset = mgr.get(code)
        if not asset:
            return {"success": False, "reply": f"资产不存在：{code}"}
        return format_single(asset)

    # === 入库命令 ===
    if any(k in text for k in ["入库", "新增", "添加", "买", "采购"]):
        return parse_add(text, mgr)

    # === 领用命令 ===
    if "领用" in text or "发给" in text or "分配给" in text:
        return parse_assign(text, mgr)

    # === 调拨命令 ===
    if "调拨" in text or "调给" in text or "转移给" in text:
        return parse_transfer(text, mgr)

    # === 闲置命令 ===
    if "闲置" in text or "封存" in text:
        code = extract_code(text)
        if not code:
            return {"success": False, "reply": "请告诉我要闲置的资产编码，如：MY-2026-0001"}
        return mgr.idle(code, remarks="对话闲置")

    # === 维保命令 ===
    if "维保" in text or "维修" in text:
        code = extract_code(text)
        if not code:
            return {"success": False, "reply": "请告诉我要维保的资产编码"}
        return mgr.repair(code, remarks="对话维保")

    # === 处置命令 ===
    if "处置" in text or "报废" in text or "卖掉" in text or "捐赠" in text:
        code = extract_code(text)
        if not code:
            return {"success": False, "reply": "请告诉我要处置的资产编码"}
        method = "scrap"
        if "卖掉" in text or "回收" in text:
            method = "resell"
        elif "捐赠" in text:
            method = "donate"
        return mgr.dispose(code, method=method, remarks="对话处置")

    # === 归还命令 ===
    if "归还" in text or "退库" in text:
        code = extract_code(text)
        if not code:
            return {"success": False, "reply": "请告诉我要归还的资产编码"}
        return mgr.idle(code, remarks="归还退库")

    # === 帮助 ===
    if "帮助" in text or "help" in text.lower():
        return {
            "success": True,
            "reply": """📋 资产管理指令集：

【查询】
• "小王有几台设备" → 查询名下资产
• "MY-2026-0001" → 查询单条资产
• "搜索苹果" → 关键词搜索
• "闲置资产" → 查询可分配资产
• "资产统计" → 全局统计

【入库】
• "入库一台MacBook Pro给小王" → 新增并领用
• "新增一台显示器，品牌Apple" → 仅入库

【流转】
• "把MY-2026-0001调给小李" → 调拨
• "MY-2026-0001闲置了" → 闲置封存
• "MY-2026-0001处置了" → 处置退出
• "MY-2026-0001维保了" → 进入维保
• "MY-2026-0001归还了" → 归还退库"""
        }

    return {
        "success": False,
        "reply": f"没听懂你说的是什么意思，可以试试：\n• '小王有几台设备'\n• '入库一台MacBook Pro'\n• 'MY-2026-0001调给小李'\n• '资产统计'\n• 输入'帮助'查看全部指令"
    }


def parse_add(text: str, mgr: AssetManager) -> dict:
    """解析入库命令"""
    import re
    # 尝试提取人名（"入库给小王"、"新增给小王"）
    assignee = ""
    for kw in ["给", "发给", "分配给"]:
        idx = text.find(kw)
        if idx > 0:
            after = text[idx+1:].strip()
            assignee = re.split(r"[，,。]", after)[0].strip()
            text = text[:idx].strip()
            break

    # 提取设备类型
    asset_type = "other"
    if any(k in text for k in ["笔记本", "MacBook", "电脑"]):
        asset_type = "laptop"
    elif any(k in text for k in ["台式机", "台式", "PC"]):
        asset_type = "desktop"
    elif "显示器" in text:
        asset_type = "monitor"
    elif "手机" in text:
        asset_type = "phone"
    elif "平板" in text:
        asset_type = "tablet"
    elif any(k in text for k in ["键鼠", "键盘", "鼠标"]):
        asset_type = "keyboard_mouse"
    elif "打印" in text:
        asset_type = "printer"

    # 提取品牌
    brand = ""
    for b in ["Apple", "苹果", "联想", "Lenovo", "Dell", "惠普", "HP", "华为", "小米"]:
        if b in text:
            brand = b
            break

    name = text.replace("入库", "").replace("新增", "").replace("添加", "").replace("采购", "").replace("一台", "").replace("一台", "").strip()
    if not name:
        name = AssetType(asset_type).label

    asset = Asset(
        name=name,
        asset_type=asset_type,
        brand=brand,
        assignee=assignee,
        status="in_use" if assignee else "in_stock",
    )

    result = mgr.add(asset)
    if result["success"] and assignee:
        mgr.assign(result["asset_id"], assignee, "", "")
        return {
            "success": True,
            "reply": f"✅ 资产[{name}]已入库并发放给「{assignee}」，编码：{result['asset_id']}"
        }
    return result


def parse_assign(text: str, mgr: AssetManager) -> dict:
    """解析领用命令"""
    import re
    # "发给小王 MY-2026-0001" 或 "MY-2026-0001发给小王"
    code = extract_code(text)
    parts = text.replace("领用", "").replace("发给", "").replace("分配给", "").replace(code, "").strip()
    name_parts = re.split(r"[，,。]", parts)
    assignee = name_parts[0].strip()
    department = name_parts[1].strip() if len(name_parts) > 1 else ""

    if not code:
        return {"success": False, "reply": "请告诉我要领用的资产编码，如：'发给小王 MY-2026-0001'"}
    if not assignee:
        return {"success": False, "reply": "请告诉我要发给谁"}

    return mgr.assign(code, assignee, department)


def parse_transfer(text: str, mgr: AssetManager) -> dict:
    """解析调拨命令"""
    import re
    code = extract_code(text)
    parts = text.replace("调拨", "").replace("调给", "").replace("转移给", "").replace(code, "").strip()
    name_parts = re.split(r"[，,。]", parts)
    new_assignee = name_parts[0].strip()
    new_dept = name_parts[1].strip() if len(name_parts) > 1 else ""

    if not code:
        return {"success": False, "reply": "请告诉我要调拨的资产编码，如：'MY-2026-0001调给小李'"}
    if not new_assignee:
        return {"success": False, "reply": "请告诉我要调给谁"}

    return mgr.transfer(code, new_assignee, new_dept)


def extract_code(text: str) -> str:
    """从文本中提取资产编码"""
    import re
    match = re.search(r"MY-\d{4}-\d{4}", text)
    return match.group(0) if match else ""


def format_single(asset: dict) -> dict:
    """格式化单条资产显示"""
    status_label = AssetStatus(asset["status"]).label if asset["status"] in [e.value for e in AssetStatus] else asset["status"]
    dept_str = f"（{asset['department']}）" if asset.get("department") else ""
    assignee_str = f"{asset.get('assignee','')}{dept_str}" if asset.get('assignee') else "—"
    seat_str = asset.get('seat_number', '—')
    value_str = f"¥{asset.get('purchase_price', 0):,.2f}" if asset.get('purchase_price') else "—"
    warranty = asset.get('warranty_expire', '—')
    remarks = f"\n备注：{asset['remarks']}" if asset.get('remarks') else ""

    lines = [
        f"📦 资产详情 [{asset['asset_id']}]",
        f"名称：{asset['name']}",
        f"类型：{AssetType(asset['asset_type']).label if asset['asset_type'] in [e.value for e in AssetType] else asset['asset_type']}",
        f"品牌型号：{asset.get('brand','—')} {asset.get('model','—')}".strip(),
        f"序列号：{asset.get('serial_number','—')}",
        f"状态：{status_label}",
        f"使用人：{assignee_str}",
        f"工位：{seat_str}",
        f"采购价格：{value_str}",
        f"采购日期：{asset.get('purchase_date','—')}",
        f"质保到期：{warranty}",
        f"条码：{asset.get('barcode','—')}",
        f"创建时间：{asset.get('created_at','—')[:10]}{remarks}",
    ]

    return {
        "success": True,
        "reply": "\n".join(lines),
        "data": asset
    }


def format_list(assets: List[dict], title: str = "") -> dict:
    """格式化资产列表显示"""
    lines = [f"📋 {title}"]
    for i, a in enumerate(assets[:20], 1):
        status_label = AssetStatus(a["status"]).label if a["status"] in [e.value for e in AssetStatus] else a["status"]
        assignee = a.get("assignee", "—")
        dept = a.get("department", "")
        dept_str = f"({dept})" if dept else ""
        value = f"¥{a.get('purchase_price',0):,.0f}" if a.get("purchase_price") else ""
        lines.append(
            f"{i}. [{a['asset_id']}] {a['name']} | {status_label} | {assignee}{dept_str} {value}"
        )

    if len(assets) > 20:
        lines.append(f"...还有 {len(assets) - 20} 条")

    total_value = sum(a.get('purchase_price', 0) for a in assets)
    lines.append(f"\n共 {len(assets)} 台，总价值 ¥{total_value:,.2f}")

    return {"success": True, "reply": "\n".join(lines), "data": assets[:20]}


# ============ CLI入口 ============
if __name__ == "__main__":
    # 命令行测试
    print("=" * 50)
    print("IT 资产管理系统资产管理系统 v1.0 — 对话式交互")
    print("=" * 50)

    while True:
        try:
            cmd = input("\n请输入指令（输入q退出）：\n> ").strip()
            if cmd in ["q", "quit", "exit"]:
                break
            if not cmd:
                continue
            result = parse_command(cmd)
            print(f"\n{'=' * 40}")
            print(result["reply"])
            if not result["success"] and result.get("data"):
                print(f"调试信息: {result['data']}")
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\n执行出错：{e}")

    print("\n再见！")
