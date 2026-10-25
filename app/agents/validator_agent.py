"""NumericValidatorAgent（数值校验智能体）。

职责（需求文档 3.4）：
- 关键：确定性规则优先，LLM 只做辅助解读（防幻觉）；
- 硬规则用 numeric_rules 工具校验（100% 可靠）；
- 输出校验报告，block 级异常阻断流水线。
"""
from app.llm import call_llm_json
from app.state import GamePlanState
from app.tools.numeric_rules import validate_monsters, summarize

SYSTEM_PROMPT = """你是游戏策划流水线中的「数值 Agent（NumericValidatorAgent）」。

根据世界观与关卡设计，生成怪物战斗数值配置（血量、攻击、防御、金币、掉落爆率）。

输出 JSON（严格按此结构）：
{
  "player_max_hp": 100,
  "monsters": [
    {
      "id": "goblin_01",
      "name": "哥布林小兵",
      "hp": 30,
      "attack": 5,
      "defense": 1,
      "gold": 10,
      "drops": [{"item": "草药", "rate": 30}, {"item": "铜币", "rate": 50}]
    }
  ],
  "difficulty_note": "难度曲线说明（LLM 软评估，仅供参考）"
}

硬性要求：
1. 数值必须合理：hp/attack/defense 非负；
2. 单个怪物攻击不能达到玩家最大血量的 50%（不能秒杀）；
3. 单只怪掉落爆率总和不能超过 100%；
4. 金币掉落不超过 500（防通胀）；
5. 新手关卡（玩家 1-3 级）难度应偏低。
"""


def run_validator(state: GamePlanState) -> dict:
    world = state.get("world_setting") or {}

    # 1) LLM 生成数值配置
    result = call_llm_json(
        SYSTEM_PROMPT,
        f"世界观：{world}\n请生成怪物数值配置 JSON。",
        temperature=0.2,
        max_retries=2,
    )

    player_hp = int(result.get("player_max_hp", 100) or 100)
    monsters = result.get("monsters") or []

    # 2) 确定性硬规则校验（不依赖 LLM）
    issues = validate_monsters(monsters, player_max_hp=player_hp)
    summary = summarize(issues)

    validate_report = {
        "player_max_hp": player_hp,
        "difficulty_note": result.get("difficulty_note", ""),
        "passed": summary["passed"],
        "block_count": summary["block_count"],
        "warning_count": summary["warning_count"],
        "issues": summary["issues"],
    }

    error_log = list(state.get("error_log") or [])
    for it in issues:
        if it["level"] == "block":
            error_log.append(f"[Validator] 阻断: {it['monster_id']} - {it['message']}")

    return {
        "monster_numeric_data": result,
        "validate_report": validate_report,
        "current_stage": "validator",
        "error_log": error_log,
    }
