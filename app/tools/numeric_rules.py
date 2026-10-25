"""怪物/战斗数值硬规则校验（确定性，不依赖 LLM）。

对应需求文档 3.4「硬规则」：
1. 血量、攻击、防御不能低于 0
2. 掉落爆率总和不能 > 100%
3. 新手关卡怪物不能秒杀玩家（伤害阈值）
4. 单局奖励金币不能超过上限（防通胀）

每个问题带等级：block（阻断，必须修） / warning（警告，可继续）。
"""
from typing import Iterable


# 默认阈值（可通过参数覆盖）
DEFAULT_SINGLE_HIT_RATIO = 0.5   # 单次伤害不得超过玩家最大血量的 50%，否则算"秒杀风险"
DEFAULT_GOLD_CAP = 500           # 单只怪金币掉落上限


def validate_monsters(
    monsters: Iterable[dict],
    player_max_hp: int = 100,
    gold_cap: int = DEFAULT_GOLD_CAP,
    single_hit_ratio: float = DEFAULT_SINGLE_HIT_RATIO,
) -> list[dict]:
    """校验怪物列表，返回问题清单。

    monster 结构约定:
        {
            "id": "goblin_01",
            "name": "哥布林小兵",
            "hp": 30,
            "attack": 5,
            "defense": 1,
            "gold": 10,
            "drops": [{"item": "herb", "rate": 30}, ...],  # rate 单位 %
        }

    返回:
        [{"monster_id": ..., "level": "block"|"warning",
          "rule": "...", "message": "...", "suggest": "..."}]
    """
    issues: list[dict] = []
    threshold = player_max_hp * single_hit_ratio

    for m in monsters:
        mid = m.get("id", "unknown")
        name = m.get("name", "")

        def add(level: str, rule: str, msg: str, suggest: str = ""):
            issues.append({
                "monster_id": mid,
                "monster_name": name,
                "level": level,
                "rule": rule,
                "message": msg,
                "suggest": suggest,
            })

        # 规则 1：基础数值非负
        for field in ("hp", "attack", "defense"):
            v = m.get(field, 0)
            if not isinstance(v, (int, float)) or v < 0:
                add("block", f"{field}_negative",
                    f"{field} 值为 {v}，不能为负",
                    f"将 {field} 设为 >= 0 的整数")

        # 规则 2：爆率总和 <= 100%
        drops = m.get("drops", []) or []
        total_rate = sum(float(d.get("rate", 0)) for d in drops)
        if total_rate > 100:
            add("block", "drop_rate_overflow",
                f"掉落爆率总和 {total_rate}% > 100%",
                f"将总爆率调整到 <= 100%（当前超出 {total_rate - 100}%）")

        # 规则 3：不能秒杀玩家
        atk = m.get("attack", 0)
        if isinstance(atk, (int, float)) and atk >= threshold:
            add("block", "one_shot",
                f"攻击 {atk} >= 玩家血量阈值 {threshold:.1f}（{player_max_hp} 的 {single_hit_ratio:.0%}），存在秒杀风险",
                f"建议将攻击降到 < {threshold:.1f}")

        # 规则 4：金币上限
        gold = m.get("gold", 0)
        if isinstance(gold, (int, float)) and gold > gold_cap:
            add("warning", "gold_overflow",
                f"金币掉落 {gold} 超过单只上限 {gold_cap}",
                f"建议将金币降到 <= {gold_cap}，防止经济通胀")

    return issues


def summarize(issues: list[dict]) -> dict:
    """汇总校验结果。"""
    blocks = [i for i in issues if i["level"] == "block"]
    warnings = [i for i in issues if i["level"] == "warning"]
    return {
        "passed": len(blocks) == 0,
        "block_count": len(blocks),
        "warning_count": len(warnings),
        "issues": issues,
    }
