"""测试 MapAgent 的工具调用（Function Calling）。

只跑 MapAgent 一步，快（1 次 LLM 调用）。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agents.map_agent import run_map
from app.state import initial_state


def main():
    print("=" * 60)
    print("测试 MapAgent 工具调用")
    print("=" * 60)

    state = initial_state("设计一个新手森林关卡", project_id="test")
    state["world_setting"] = {
        "theme": "森林",
        "difficulty": "偏低",
        "player_level_range": "1-3",
    }
    state["task_list"] = [{"agent": "map", "task": "设计新手森林关卡地图"}]

    result = run_map(state)
    m = result["map_data"]

    print("\n【日志】")
    for e in result.get("error_log", []):
        print("  -", e)

    print("\n【地图数据】")
    print("  尺寸:", m.get("width"), "×", m.get("height"))
    print("  房间数:", len(m.get("regions_layout") or {}))
    print("  刷点:", len(m.get("spawn_points") or []), "个")
    print("  资源点:", len(m.get("resource_points") or []), "个")
    print("  起点(row,col):", m.get("_start_rc"), " 终点:", m.get("_end_rc"))
    print("  BFS:", m.get("_path_check", {}).get("message"))

    grid = m.get("grid") or []
    if grid:
        print("\n【地图预览】（#=墙  .=路）")
        for row in grid[:12]:
            print("  " + "".join("#" if c else "." for c in row))

    assert grid, "grid 为空"
    assert m.get("_path_check", {}).get("reachable"), "地图不连通"
    print("\n✅ MapAgent 工具调用测试通过")


if __name__ == "__main__":
    main()
