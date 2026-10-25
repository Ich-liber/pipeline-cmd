"""2D 像素地图确定性生成器。

算法：随机房间 + L 型走廊连接（经典地牢生成），保证：
- 起点到终点必然连通（房间按顺序连接）
- 无重叠、无封闭死区
- 输出 grid(0=可通行,1=障碍) + 区域 + 刷点/资源点

这是 MapAgent 的「工具」：LLM 只决定参数（尺寸/主题/难度），
代码负责保证地图质量（连通性 100%）。
"""
import random


def generate_pixel_map(
    width: int = 20,
    height: int = 15,
    theme: str = "森林",
    difficulty: str = "偏低",
    seed: int | None = None,
) -> dict:
    """生成一张 2D 像素关卡地图。

    返回:
        {
          "width", "height", "grid"(二维 0/1),
          "regions": {"start": [x,y], "end": [x,y]},
          "_start_rc": [row,col], "_end_rc": [row,col],
          "spawn_points": [...], "resource_points": [...],
          "regions_layout": {...}, "description": str
        }
    """
    width = max(12, min(int(width), 30))
    height = max(10, min(int(height), 20))
    rng = random.Random(seed if seed is not None else random.randint(0, 10**9))

    grid = [[1] * width for _ in range(height)]  # 1=墙

    # ---------- 1. 随机房间（不重叠） ----------
    rooms = []
    for _ in range(60):
        w = rng.randint(3, 6)
        h = rng.randint(3, 5)
        if w + 2 >= width or h + 2 >= height:
            continue
        x = rng.randint(1, width - w - 1)
        y = rng.randint(1, height - h - 1)
        # 与已有房间保持 1 格间隔
        overlap = False
        for rx, ry, rw, rh in rooms:
            if not (x + w + 1 < rx or rx + rw + 1 < x or y + h + 1 < ry or ry + rh + 1 < y):
                overlap = True
                break
        if overlap:
            continue
        rooms.append((x, y, w, h))
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                grid[yy][xx] = 0
        if len(rooms) >= 6:
            break

    if len(rooms) < 2:  # 兜底：至少两个房间
        rooms = [(1, 1, 4, 3), (width - 6, height - 5, 4, 3)]
        for rx, ry, rw, rh in rooms:
            for yy in range(ry, ry + rh):
                for xx in range(rx, rx + rw):
                    grid[yy][xx] = 0

    # ---------- 2. 走廊连接（保证连通） ----------
    def carve_h(x1, x2, y):
        for x in range(min(x1, x2), max(x1, x2) + 1):
            grid[y][x] = 0

    def carve_v(y1, y2, x):
        for y in range(min(y1, y2), max(y1, y2) + 1):
            grid[y][x] = 0

    for i in range(1, len(rooms)):
        x1, y1, w1, h1 = rooms[i - 1]
        x2, y2, w2, h2 = rooms[i]
        cx1, cy1 = x1 + w1 // 2, y1 + h1 // 2
        cx2, cy2 = x2 + w2 // 2, y2 + h2 // 2
        if rng.random() < 0.5:
            carve_h(cx1, cx2, cy1)
            carve_v(cy1, cy2, cx2)
        else:
            carve_v(cy1, cy2, cx1)
            carve_h(cx1, cx2, cy2)

    # ---------- 3. 起点 / 终点 ----------
    sx, sy, sw, sh = rooms[0]
    ex, ey, ew, eh = rooms[-1]
    start = (sy + sh // 2, sx + sw // 2)          # (row, col)
    end = (ey + eh // 2, ex + ew // 2)

    # ---------- 4. 区域分配（按房间顺序） ----------
    region_names = ["起始区", "战斗区", "战斗区", "休息区", "BOSS区", "出口区"]
    regions_layout = {}
    for idx, (x, y, w, h) in enumerate(rooms):
        name = region_names[min(idx, len(region_names) - 1)]
        regions_layout[name] = {"x": x, "y": y, "w": w, "h": h}

    # ---------- 5. 怪物刷点 / 资源点 ----------
    spawn_points, resource_points = [], []
    for idx, (x, y, w, h) in enumerate(rooms):
        if idx == 0:      # 起始区不放怪
            resource_points.append({"x": x + 1, "y": y + 1, "type": "草药"})
            continue
        is_boss = idx == len(rooms) - 1
        count = 1 if is_boss else rng.randint(1, 3)
        spawn_points.append({
            "x": x + w // 2,
            "y": y + h // 2,
            "monster": f"{theme}首领" if is_boss else f"{theme}小怪",
            "count": count,
        })
        if idx % 2 == 1:
            resource_points.append({"x": x + 1, "y": y + 1,
                                    "type": "宝箱" if rng.random() < 0.5 else "草药"})

    return {
        "width": width,
        "height": height,
        "grid": grid,
        "regions": {"start": [start[1], start[0]], "end": [end[1], end[0]]},  # [x, y]
        "_start_rc": list(start),
        "_end_rc": list(end),
        "regions_layout": regions_layout,
        "spawn_points": spawn_points,
        "resource_points": resource_points,
        "generator": "generate_pixel_map",
        "description": f"{theme}主题像素关卡：{len(rooms)} 个房间由走廊连接，"
                       f"起点→战斗区→休息区→BOSS区→出口，难度{difficulty}。",
    }
