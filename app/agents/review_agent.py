"""ReviewAgent（综合评审智能体）。

职责（需求文档 3.5）：
- 聚合地图、对话、数值三部分产出；
- 检查剧情连贯性、世界观一致性；
- 汇总 Validator 的数值风险；
- 输出结论：【通过】或【驳回 + 修改清单】。
"""
import json

from app.llm import call_llm_json
from app.state import GamePlanState

SYSTEM_PROMPT = """你是游戏策划流水线中的「评审 Agent（ReviewAgent）」。

通读地图、对话、数值三部分产出，做综合评审。

输出 JSON（严格按此结构）：
{
  "conclusion": "pass" 或 "reject",
  "score": 0-100 的整数,
  "issues": [
    {"level": "block|warning", "part": "map|dialogue|numeric|overall", "message": "问题描述"}
  ],
  "suggestions": ["修改建议1", "修改建议2"],
  "summary": "一句话评审总结"
}

评审标准：
1. 地图：起点到终点可达，无死区；
2. 对话：NPC 人设一致，覆盖任务交付；
3. 数值：无阻断级错误（秒杀/负值/爆率溢出）；
4. 整体：剧情逻辑连贯，世界观统一。

若存在 block 级问题（含数值校验阻断），必须结论为 "reject"。
"""


def run_review(state: GamePlanState) -> dict:
    map_data = state.get("map_data") or {}
    dialogue_data = state.get("dialogue_data") or {}
    validate_report = state.get("validate_report") or {}
    world = state.get("world_setting") or {}
    retry_count = int(state.get("retry_count", 0) or 0)

    # 把关键信息压缩传给 LLM，避免超长
    payload = {
        "world": world,
        "map_summary": {
            "width": map_data.get("width"),
            "height": map_data.get("height"),
            "path_check": map_data.get("_path_check"),
            "description": map_data.get("description", "")[:200],
        },
        "dialogue_summary": {
            "npcs": [
                {"name": n.get("name"), "dialogues": len(n.get("dialogues", []))}
                for n in (dialogue_data.get("npcs") or [])
            ]
        },
        "numeric_summary": {
            "passed": validate_report.get("passed"),
            "block_count": validate_report.get("block_count"),
            "warning_count": validate_report.get("warning_count"),
            "issues": validate_report.get("issues", [])[:5],
        },
    }

    result = call_llm_json(
        SYSTEM_PROMPT,
        f"请评审以下产出：\n{json.dumps(payload, ensure_ascii=False, indent=2)}",
        temperature=0.2,
        max_retries=2,
    )

    # 确定性兜底：数值有阻断或地图不可达 → 强制 reject
    hard_reject = (
        not (validate_report.get("passed", True))
        or not (map_data.get("_path_check", {}) or {}).get("reachable", True)
    )
    conclusion = result.get("conclusion", "reject")
    if hard_reject:
        conclusion = "reject"
        result.setdefault("issues", []).append(
            {"level": "block", "part": "overall",
             "message": "确定性规则判定未通过（数值阻断或地图不可达）"}
        )

    return {
        "review_report": result,
        "review_status": conclusion,
        "current_stage": "review",
        "retry_count": retry_count + (1 if conclusion == "reject" else 0),
        "error_log": list(state.get("error_log") or []),
    }
