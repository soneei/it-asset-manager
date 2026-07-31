#!/usr/bin/env python3
"""核心逻辑测试：折旧 / 状态机 / 审计回放（不污染生产库，使用临时库）

运行：python3 test_core.py
依赖：仅标准库
"""
import sys
import os
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import asset_manager as am


def test_depreciation():
    """折旧计算（直线法）与可信标志"""
    # 正常：2024-01-01 买 10000，折旧3年
    a = am.Asset(asset_id="T-1", name="测试机", purchase_date="2024-01-01",
                 purchase_price=10000.0, depreciation_years=3)
    v = a.current_depreciation
    assert 0 < v < 10000, f"折旧值异常: {v}"
    assert a.depreciation_reliable is True

    # 无采购价 -> 0
    b = am.Asset(asset_id="T-2", name="测试机", purchase_date="2024-01-01", purchase_price=0)
    assert b.current_depreciation == 0.0

    # 无采购日期 -> 0
    c = am.Asset(asset_id="T-3", name="测试机", purchase_price=10000.0, depreciation_years=3)
    assert c.current_depreciation == 0.0

    # 折旧年限为0 -> 返回原价但不可信（修复后不再静默）
    d = am.Asset(asset_id="T-4", name="测试机", purchase_date="2024-01-01",
                 purchase_price=5000.0, depreciation_years=0)
    assert d.current_depreciation == 5000.0
    assert d.depreciation_reliable is False

    # 日期格式错 -> 返回原价但不可信
    e = am.Asset(asset_id="T-5", name="测试机", purchase_date="2024/01/01",
                 purchase_price=5000.0, depreciation_years=3)
    assert e.current_depreciation == 5000.0
    assert e.depreciation_reliable is False
    print("✅ 折旧测试通过")


def test_status_history():
    """状态机历史追加"""
    a = am.Asset(asset_id="T-6", name="测试机")
    a.add_status_history("in_stock", "in_use", "猫猫", "领用")
    assert len(a.status_history) == 1
    assert a.status_history[0]["to_status"] == "in_use"
    a.add_status_history("in_use", "idle", "猫猫", "闲置")
    assert len(a.status_history) == 2
    print("✅ 状态机测试通过")


def test_audit_replay():
    """审计回放：新增+领用应留下可回溯的 operation_log"""
    tmp = tempfile.mkdtemp()
    db = os.path.join(tmp, "test_assets.db")
    js = os.path.join(tmp, "test_assets.json")
    am.DB_PATH = db
    am.JSON_PATH = js
    am.init_db()

    mgr = am.AssetManager(operator="测试员")
    r = mgr.add(am.Asset(asset_id="AUD-1", name="审计机", assignee="张三", department="技术部"))
    assert r.get("success") is True, f"add 失败: {r}"
    mgr.assign("AUD-1", "李四", "市场部", "XM11D011")

    logs = am.get_operation_log(asset_id="AUD-1")
    assert len(logs) >= 2, f"审计记录不足: {len(logs)}"
    ops = [l["operation"] for l in logs]
    assert "入库" in ops and "领用" in ops, f"操作类型缺失: {ops}"

    summary = am.get_audit_summary()
    assert "by_operator" in summary and "by_operation_type" in summary
    assert summary["total_entries"] >= 2
    print("✅ 审计回放测试通过")

    for f in (db, js):
        try:
            os.remove(f)
        except OSError:
            pass


if __name__ == "__main__":
    test_depreciation()
    test_status_history()
    test_audit_replay()
    print("\n🎉 全部核心测试通过")
