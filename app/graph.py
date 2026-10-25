"""LangGraph 状态机编排。

流程（需求文档 2.1）：
    planner → map → dialogue → validator → review
                                              ├─ pass → END
                                              └─ reject → planner（带评审意见迭代，最多 MAX_ITERATIONS 轮）

说明：需求文档提到 Map 与 Dialogue 可并行，MVP 阶段先串行跑通；
后续可用 LangGraph 的并行分支优化。
"""
from langgraph.graph import StateGraph, END

from app.config import settings
from app.state import GamePlanState
from app.agents.planner import run_planner
from app.agents.map_agent import run_map
from app.agents.dialogue_agent import run_dialogue
from app.agents.validator_agent import run_validator
from app.agents.review_agent import run_review


def route_after_review(state: GamePlanState) -> str:
    """评审后的路由：通过 / 驳回重来 / 超过上限强制结束。"""
    if state.get("review_status") == "pass":
        return "pass"
    if int(state.get("retry_count", 0) or 0) >= settings.MAX_ITERATIONS:
        return "pass"  # 达到最大迭代次数，强制结束（交给人工兜底）
    return "reject"


def build_graph():
    g = StateGraph(GamePlanState)

    g.add_node("planner", run_planner)
    g.add_node("map", run_map)
    g.add_node("dialogue", run_dialogue)
    g.add_node("validator", run_validator)
    g.add_node("review", run_review)

    g.set_entry_point("planner")
    g.add_edge("planner", "map")
    g.add_edge("map", "dialogue")
    g.add_edge("dialogue", "validator")
    g.add_edge("validator", "review")
    g.add_conditional_edges(
        "review",
        route_after_review,
        {"pass": END, "reject": "planner"},
    )
    return g.compile()


# 编译一次，供 API 和脚本复用
graph = build_graph()
