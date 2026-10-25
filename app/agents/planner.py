"""PlannerAgent（规划智能体）。

职责（需求文档 3.1）：
1. 解析用户原始自然语言需求，抽取关键要素；
2. 生成全局世界观设定；
3. 拆解任务清单，判定需要哪些子 Agent 执行（map / dialogue / numeric）；
4. 检测新需求与既有世界观的冲突。

输出强制 JSON 结构，字段见 SYSTEM_PROMPT。
"""
import json

from app.llm import call_llm_json
from app.rag.knowledge_base import KnowledgeBase
from app.state import GamePlanState

SYSTEM_PROMPT = """你是游戏策划流水线中的「规划 Agent（PlannerAgent）」。

你的职责：
1. 解析用户的需求描述，抽取关键要素（关卡主题、玩家等级区间、怪物、任务目标、风格、难度约束）；
2. 生成一份全局世界观设定（world_setting），供后续所有 Agent 引用；
3. 拆解任务清单（task_list），判定本次需要哪些子 Agent 执行：
   - "map"      → 需要地图/关卡设计
   - "dialogue" → 需要 NPC 对话设计
   - "numeric"  → 需要战斗数值设计
4. 若用户需求与既有世界观冲突，在 warnings 中说明。

你必须只输出如下 JSON（不要任何解释文字、不要 markdown 代码块外的内容）：

{
  "world_setting": {
    "theme": "关卡主题",
    "style": "画面/玩法风格",
    "difficulty": "难度定位",
    "player_level_range": "玩家等级区间，如 1-3",
    "lore": "世界观背景描述，2-4 句",
    "factions": ["相关阵营/势力"]
  },
  "key_elements": {
    "monsters": ["怪物列表"],
    "quest_goal": "主线任务目标",
    "rewards": ["奖励描述"]
  },
  "task_list": [
    {"agent": "map", "task": "该子任务具体要做什么"},
    {"agent": "dialogue", "task": "..."},
    {"agent": "numeric", "task": "..."}
  ],
  "warnings": []
}
"""


def run_planner(state: GamePlanState) -> dict:
    """执行规划，返回要合并进全局 State 的增量字段。

    流程（含 RAG）：
    ① 检索历史设定 → ② 注入 Prompt（防冲突）→ ③ 生成 → ④ 新设定沉淀回知识库
    """
    user_prompt = state.get("user_raw_prompt", "")
    project_id = state.get("project_id", "default")

    # ---------- ① RAG：检索历史设定（按项目隔离） ----------
    kb = None
    history_hits = []
    history_text = "（无历史设定）"
    try:
        kb = KnowledgeBase(persist_dir="data/chroma")
        history_hits = kb.search(user_prompt, top_k=3, project_id=project_id)
        if history_hits:
            history_text = "\n".join(f"- {h['text']}" for h in history_hits)
    except Exception as e:  # noqa: BLE001
        history_text = f"（历史设定检索失败：{e}）"

    # ---------- ② 组装上下文 ----------
    context = f"\n【历史设定检索结果（新内容不得与之冲突）】\n{history_text}"

    # 若 State 里已有世界观，也一并传入
    existing = state.get("world_setting") or {}
    if existing:
        context += f"\n【当前已有世界观（新内容不得与之冲突）】\n{json.dumps(existing, ensure_ascii=False)}"

    result = call_llm_json(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=f"用户需求：{user_prompt}{context}",
        temperature=0.4,
    )

    # 结构兜底：缺字段时给默认值
    world = result.get("world_setting") or {}
    tasks = result.get("task_list") or []
    if not tasks:
        tasks = [
            {"agent": "map", "task": "设计关卡地图"},
            {"agent": "dialogue", "task": "设计 NPC 对话"},
            {"agent": "numeric", "task": "设计战斗数值"},
        ]

    # ---------- ③ RAG：把新世界观沉淀回知识库 ----------
    if kb is not None:
        try:
            kb.add_world(state.get("request_id", "unknown"), world, project_id=project_id)
        except Exception:  # noqa: BLE001
            pass

    # ---------- ④ 记录日志 ----------
    log = list(state.get("error_log") or [])
    if history_hits:
        log.append(f"[Planner] RAG 检索到 {len(history_hits)} 条历史设定")
    log.extend(result.get("warnings") or [])

    return {
        "world_setting": world,
        "task_list": tasks,
        "current_stage": "planner",
        "error_log": log,
    }
