"""MapAgent（地图关卡智能体）—— 工具调用版。

核心变化（Function Calling）：
- 不再让 LLM 直接输出 300 个网格数字（不可靠，曾出现终点越界）；
- LLM 决定参数（尺寸/主题/难度），调用确定性工具 `generate_pixel_map` 生成地图；
- 工具保证连通性，代码再做 BFS 复核（双保险）。

人机分工：LLM 负责"决策"，代码负责"质量保证"。
"""
import json

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from app.llm import get_llm
from app.state import GamePlanState
from app.tools.map_generator import generate_pixel_map
from app.tools.path_check import check_path

SYSTEM_PROMPT = """你是游戏策划流水线中的「地图 Agent（MapAgent）」。

你的任务：根据世界观设计一张 2D 像素风格关卡地图。

规则（重要）：
1. 你【不要】自己绘制网格数据（grid）。你有一个工具 `generate_pixel_map`，
   它用确定性算法生成保证连通的地图。
2. 你只需要决定工具参数：
   - width：地图宽度（12-30，新手关卡建议 18-22）
   - height：地图高度（10-20，新手关卡建议 14-16）
   - theme：主题（如 森林/洞穴/地下城/废墟）
   - difficulty：难度（偏低/中等/偏高）
3. 调用工具后你会收到完整地图数据，请基于它简短说明布局。

请立即调用 generate_pixel_map 生成地图。"""

MAP_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "generate_pixel_map",
        "description": "生成一张 2D 像素风格关卡地图（房间+走廊确定性算法，保证起点到终点连通）",
        "parameters": {
            "type": "object",
            "properties": {
                "width": {"type": "integer", "description": "地图宽度（12-30）"},
                "height": {"type": "integer", "description": "地图高度（10-20）"},
                "theme": {"type": "string", "description": "主题，如 森林/洞穴/地下城"},
                "difficulty": {"type": "string", "description": "难度，如 偏低/中等"},
            },
            "required": ["width", "height", "theme"],
        },
    },
}


def run_map(state: GamePlanState) -> dict:
    """通过 Function Calling 调用地图生成工具。"""
    world = state.get("world_setting") or {}
    tasks = state.get("task_list") or []
    map_task = next((t for t in tasks if t.get("agent") == "map"), {})

    theme_hint = world.get("theme") or "森林"
    difficulty_hint = str(world.get("difficulty") or "偏低")

    llm = get_llm(temperature=0.3).bind_tools([MAP_TOOL_SCHEMA])
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(
            content=(
                f"世界观：{json.dumps(world, ensure_ascii=False)}\n"
                f"地图任务：{map_task.get('task', '设计新手关卡地图')}\n"
                f"提示：主题可用「{theme_hint}」，难度「{difficulty_hint}」。"
            )
        ),
    ]

    error_log = list(state.get("error_log") or [])
    map_data: dict | None = None

    # ---------- 第一次调用：LLM 决定是否/如何调工具 ----------
    resp = llm.invoke(messages)
    if getattr(resp, "tool_calls", None):
        tc = resp.tool_calls[0]
        args = tc.get("args") or {}
        map_data = generate_pixel_map(
            width=args.get("width", 20),
            height=args.get("height", 15),
            theme=args.get("theme", theme_hint),
            difficulty=args.get("difficulty", difficulty_hint),
        )
        # 把工具结果回传给 LLM（ReAct：观察结果）
        messages.append(resp)
        messages.append(
            ToolMessage(
                content=json.dumps(
                    {k: v for k, v in map_data.items() if k != "grid"},  # 网格太大，不回传
                    ensure_ascii=False,
                ),
                tool_call_id=tc["id"],
            )
        )
        try:
            llm.invoke(messages)  # LLM 观察结果（可选，不阻塞流程）
        except Exception:  # noqa: BLE001
            pass
        error_log.append(
            f"[MapAgent] 调用工具 generate_pixel_map（{args.get('width', 20)}×{args.get('height', 15)}，{theme_hint}）"
        )
    else:
        # 兜底：LLM 没有调用工具 → 直接按世界观生成默认地图
        map_data = generate_pixel_map(width=20, height=15, theme=theme_hint, difficulty=difficulty_hint)
        error_log.append("[MapAgent] LLM 未调用工具，已按默认参数生成地图（兜底）")

    # ---------- BFS 复核（双保险） ----------
    grid = map_data.get("grid") or []
    start_rc = map_data.get("_start_rc")
    end_rc = map_data.get("_end_rc")
    check = {"reachable": True, "message": "未提供路径信息", "path_length": -1}
    if grid and start_rc and end_rc:
        check = check_path(grid, tuple(start_rc), tuple(end_rc))
    map_data["_path_check"] = check
    if not check.get("reachable", True):
        error_log.append(f"[MapAgent] BFS 复核失败: {check.get('message')}")

    return {
        "map_data": map_data,
        "current_stage": "map",
        "error_log": error_log,
    }
