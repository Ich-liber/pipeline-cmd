"""DialogueAgent（NPC 对话智能体）。

职责（需求文档 3.3）：
- 读取世界观、NPC 人设，生成分支对话树；
- 支持条件分支（前置任务完成 / 持有道具 / 等级）；
- 人设锁死，避免 OOC；
- 输出对话配置 JSON。
"""
from app.llm import call_llm_json
from app.state import GamePlanState

SYSTEM_PROMPT = """你是游戏策划流水线中的「对话 Agent（DialogueAgent）」。

根据世界观与任务目标，为关卡中的 NPC 生成对话树。

输出 JSON（严格按此结构）：
{
  "npcs": [
    {
      "npc_id": "npc_anna",
      "name": "安娜",
      "role": "被囚禁的村民",
      "personality": "胆小善良，说话轻声细语",
      "dialogues": [
        {
          "id": "d1",
          "text": "救命…你终于来了！",
          "conditions": {"quest_step": "start"},
          "options": [
            {"text": "别怕，我带你出去", "next": "d2"},
            {"text": "先说说发生了什么", "next": "d3"}
          ]
        },
        {
          "id": "d2",
          "text": "谢谢你！我在东边的树洞里等你。",
          "conditions": {},
          "options": []
        }
      ]
    }
  ]
}

硬性要求：
1. 同一 NPC 的人设必须前后一致，禁止 OOC（例如胆小 NPC 突然狂暴）；
2. 对话节点要覆盖：起始对话、选项分支、任务交付；
3. npc_id 唯一；
4. 每个节点必须有 id、text、options（可为空数组）。
"""


def run_dialogue(state: GamePlanState) -> dict:
    world = state.get("world_setting") or {}
    tasks = state.get("task_list") or []
    dialogue_task = next((t for t in tasks if t.get("agent") == "dialogue"), {})

    user_prompt = (
        f"世界观：{world}\n"
        f"本次对话任务：{dialogue_task.get('task', '生成关卡 NPC 对话')}\n"
        "请生成 NPC 对话树 JSON。"
    )

    result = call_llm_json(SYSTEM_PROMPT, user_prompt, temperature=0.7, max_retries=2)

    npcs = result.get("npcs") or []
    error_log = list(state.get("error_log") or [])
    if not npcs:
        error_log.append("[DialogueAgent] 未生成 NPC 对话")

    return {
        "dialogue_data": result,
        "current_stage": "dialogue",
        "error_log": error_log,
    }
