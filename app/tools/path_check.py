"""地图路径校验（BFS）。

不依赖 LLM，纯 Python 实现。用途：
- MapAgent 生成地图后，校验是否存在从起点到终点的可通行路径；
- 标记死胡同（走不出去的区域），防止产出无解地图。

网格约定：
- 0 = 可通行
- 1 = 障碍（墙 / 不可通行）
"""
from collections import deque
from typing import Sequence


def check_path(
    grid: Sequence[Sequence[int]],
    start: tuple,
    end: tuple,
) -> dict:
    """BFS 检查 start 能否到达 end。

    参数:
        grid: 二维数组，0 可通行，1 障碍
        start: (row, col)
        end:   (row, col)

    返回:
        {
            "reachable": bool,
            "path_length": int,       # 最短步数，-1 表示不可达
            "dead_ends": list,        # 可达区域内走不到出口的格子数（近似死区）
            "message": str,
        }
    """
    rows, cols = len(grid), len(grid[0]) if grid else 0

    def in_bounds(r, c):
        return 0 <= r < rows and 0 <= c < cols

    def walkable(r, c):
        return in_bounds(r, c) and grid[r][c] == 0

    if not walkable(*start):
        return {"reachable": False, "path_length": -1, "dead_ends": [],
                "message": f"起点 {start} 不可通行"}
    if not walkable(*end):
        return {"reachable": False, "path_length": -1, "dead_ends": [],
                "message": f"终点 {end} 不可通行（被墙挡住或越界）"}

    # BFS
    dist = {start: 0}
    q = deque([start])
    found = False
    while q:
        r, c = q.popleft()
        if (r, c) == end:
            found = True
            break
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = r + dr, c + dc
            if walkable(nr, nc) and (nr, nc) not in dist:
                dist[(nr, nc)] = dist[(r, c)] + 1
                q.append((nr, nc))

    # 死区统计：所有可达格子里，除了终点，没有出口的（简化：可达格子中四邻全是墙或越界的孤立点）
    dead_ends = []
    for (r, c), d in dist.items():
        if (r, c) == end or (r, c) == start:
            continue
        exits = sum(
            1 for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1))
            if walkable(r + dr, c + dc)
        )
        if exits <= 1:  # 只有一个来路，没有其他出口
            dead_ends.append((r, c))

    if found:
        return {
            "reachable": True,
            "path_length": dist[end],
            "dead_ends": dead_ends,
            "message": f"路径可达，最短 {dist[end]} 步",
        }
    return {
        "reachable": False,
        "path_length": -1,
        "dead_ends": dead_ends,
        "message": "地图无解：起点到终点不可达（存在不可通行的封闭区域）",
    }
