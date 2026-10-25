"""端到端流水线测试（需要 .env 配好 LLM Key）。

用法：
    python scripts/test_pipeline.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.graph import graph
from app.state import initial_state

DEMO_PROMPT = (
    "制作新手森林关卡，适合 1-3 级玩家，主线任务：救出森林里的村民安娜；"
    "怪物：哥布林小兵 8 只、哥布林首领 1 只；奖励：草药、少量铜币；"
    "难度偏低，路线简单，设置一个安全休息点。"
)


def main():
    print("=" * 60)
    print("端到端流水线测试")
    print("=" * 60)

    state = initial_state(DEMO_PROMPT)
    final = graph.invoke(state, config={"recursion_limit": 50})

    print("\n【评审结论】", final.get("review_status"))
    print("\n【评审报告】")
    print(json.dumps(final.get("review_report", {}), ensure_ascii=False, indent=2)[:1500])

    print("\n【数值校验汇总】")
    vr = final.get("validate_report", {})
    print(f"  通过: {vr.get('passed')} | 阻断: {vr.get('block_count')} | 警告: {vr.get('warning_count')}")

    print("\n【地图路径校验】")
    print(" ", final.get("map_data", {}).get("_path_check"))

    print("\n【NPC 数量】", len(final.get("dialogue_data", {}).get("npcs", [])))
    print("\n【错误日志】")
    for e in final.get("error_log", [])[:10]:
        print("  -", e)

    print("\n✅ 流水线跑通（结果见上方）")


if __name__ == "__main__":
    main()
