"""测试 PlannerAgent（需要先在 .env 配置好 LLM_API_KEY）。

用法：
    python scripts/test_planner.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agents.planner import run_planner
from app.state import initial_state

DEMO_PROMPT = (
    "制作新手森林关卡，适合 1-3 级玩家，主线任务：救出森林里的村民安娜；"
    "怪物：哥布林小兵 8 只、哥布林首领 1 只；奖励：草药、少量铜币；"
    "难度偏低，路线简单，设置一个安全休息点。"
)


def main():
    print("=" * 60)
    print("测试 PlannerAgent")
    print("输入需求:", DEMO_PROMPT[:50], "...")
    print("=" * 60)

    state = initial_state(DEMO_PROMPT)
    result = run_planner(state)

    print("\n【世界观设定】")
    print(json.dumps(result["world_setting"], ensure_ascii=False, indent=2))

    print("\n【任务清单】")
    for t in result["task_list"]:
        print(f"  - [{t.get('agent')}] {t.get('task')}")

    print("\n【警告】")
    print(result.get("error_log", []) or "无")

    # 基础校验
    assert result["world_setting"], "world_setting 为空"
    assert result["task_list"], "task_list 为空"
    print("\n✅ PlannerAgent 测试通过")


if __name__ == "__main__":
    main()
