"""冒烟测试：验证确定性工具工作正常（不需要 LLM）。"""
import sys
from pathlib import Path

# 让脚本能直接 import app 包
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.tools.path_check import check_path
from app.tools.numeric_rules import validate_monsters, summarize


def test_path():
    print("=" * 50)
    print("测试 1：BFS 路径校验")
    # 可通行地图
    grid_ok = [
        [0, 0, 0, 0],
        [1, 1, 0, 1],
        [0, 0, 0, 0],
        [0, 1, 1, 0],
    ]
    r = check_path(grid_ok, (0, 0), (3, 3))
    print("  可通行地图:", r["message"], "| 路径长度:", r["path_length"])
    assert r["reachable"] is True

    # 无解地图（终点被墙包围）
    grid_bad = [
        [0, 0, 0],
        [0, 1, 0],
        [0, 1, 1],
    ]
    r2 = check_path(grid_bad, (0, 0), (2, 0))
    print("  无解地图:", r2["message"])
    assert r2["reachable"] is True  # (2,0) 其实可达

    grid_dead = [
        [0, 0, 0],
        [1, 1, 1],
        [0, 0, 0],
    ]
    r3 = check_path(grid_dead, (0, 0), (2, 2))
    print("  完全隔断地图:", r3["message"])
    assert r3["reachable"] is False
    print("  ✅ 路径校验通过")


def test_numeric():
    print("=" * 50)
    print("测试 2：数值规则校验")
    monsters = [
        {  # 正常怪
            "id": "goblin_01", "name": "哥布林小兵",
            "hp": 30, "attack": 5, "defense": 1, "gold": 10,
            "drops": [{"item": "herb", "rate": 30}, {"item": "coin", "rate": 50}],
        },
        {  # 问题怪：负血量 + 爆率超 100% + 秒杀 + 金币超限
            "id": "boss_01", "name": "哥布林首领",
            "hp": -10, "attack": 999, "defense": 5, "gold": 9999,
            "drops": [{"item": "rare", "rate": 90}, {"item": "epic", "rate": 50}],
        },
    ]
    issues = validate_monsters(monsters, player_max_hp=100)
    result = summarize(issues)
    print(f"  阻断问题: {result['block_count']} | 警告: {result['warning_count']}")
    for it in issues:
        print(f"    [{it['level']}] {it['monster_id']}: {it['message']}")
    assert result["passed"] is False
    assert result["block_count"] >= 3
    print("  ✅ 数值校验通过")


if __name__ == "__main__":
    test_path()
    test_numeric()
    print("=" * 50)
    print("🎉 全部确定性工具测试通过")
