"""
WorkBuddy集成接口 — 资产管理系统v1.0
供WorkBuddy MCP调用

使用方式：在WorkBuddy对话框中直接说：
  "资产入库：MacBook Pro给小王"
  "小王有几台设备"
  "把MY-2026-0001调给小李"
  "资产统计"
  ...

返回值格式：纯文本字符串，直接展示给用户
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from asset_cli import parse_command


def handle(query: str, operator: str = "admin") -> str:
    """
    WorkBuddy调用入口
    query: 用户自然语言查询
    operator: 操作人（从WorkBuddy会话获取）
    返回: 纯文本回复字符串
    """
    result = parse_command(query, operator)

    if result.get("reply"):
        return result["reply"]

    if result.get("message"):
        return f"⚠️ {result['message']}"

    return "⚠️ 操作异常，请重试"


if __name__ == "__main__":
    # 命令行测试
    queries = [
        "资产统计",
        "入库一台Dell显示器给小王",
        "小王有几台设备",
        "MY-2026-0001调给小李",
        "资产统计",
        "MY-2026-0001闲置了",
        "闲置资产",
        "帮助",
    ]

    for q in queries:
        print(f"\n>>> {q}")
        print(handle(q))
