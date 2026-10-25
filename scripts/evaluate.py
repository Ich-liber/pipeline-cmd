"""评测脚本：确定性工具 + 端到端流水线。

用法：
    python scripts/evaluate.py            # 默认跑 3 个端到端用例
    python scripts/evaluate.py --e2e 5    # 跑 5 个
    python scripts/evaluate.py --skip-e2e # 只跑确定性评测（秒级）

输出：reports/eval_report.md + 控制台摘要
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.graph import graph
from app.state import initial_state
from app.tools.numeric_rules import summarize, validate_monsters
from app.tools.path_check import check_path


# ============================================================
# A. 数值规则评测
# ============================================================
def _m(**kw):
    base = {"id": "m", "name": "测试怪", "hp": 30, "attack": 5, "defense": 1,
            "gold": 10, "drops": []}
    base.update(kw)
    return base


# (名称, 怪物列表, 期望阻断数, 期望警告数)
NUMERIC_CASES = [
    ("正常怪", [_m()], 0, 0),
    ("HP 为负", [_m(hp=-5)], 1, 0),
    ("攻击为负", [_m(attack=-2)], 1, 0),
    ("防御为负", [_m(defense=-1)], 1, 0),
    ("爆率 120%", [_m(drops=[{"item": "a", "rate": 80}, {"item": "b", "rate": 40}])], 1, 0),
    ("爆率恰好 100%", [_m(drops=[{"item": "a", "rate": 60}, {"item": "b", "rate": 40}])], 0, 0),
    ("攻击秒杀（>=50）", [_m(attack=60)], 1, 0),
    ("金币超限（>500）", [_m(gold=9999)], 0, 1),
    ("金币恰好 500", [_m(gold=500)], 0, 0),
    ("多怪混合（1 阻断）", [_m(id="a"), _m(id="b", hp=-1)], 1, 0),
    ("多怪混合（2 阻断）", [_m(id="a", hp=-1), _m(id="b", attack=99)], 2, 0),
    ("全部正常（3 只）", [_m(id="a"), _m(id="b"), _m(id="c")], 0, 0),
]


def eval_numeric() -> dict:
    rows, ok_cases = [], 0
    for name, monsters, exp_block, exp_warn in NUMERIC_CASES:
        issues = validate_monsters(monsters, player_max_hp=100)
        s = summarize(issues)
        ok = (s["block_count"] == exp_block) and (s["warning_count"] == exp_warn)
        ok_cases += 1 if ok else 0
        rows.append({
            "case": name,
            "expect": f"阻断{exp_block}/警告{exp_warn}",
            "actual": f"阻断{s['block_count']}/警告{s['warning_count']}",
            "pass": ok,
        })
    return {"total": len(NUMERIC_CASES), "passed": ok_cases,
            "rate": ok_cases / len(NUMERIC_CASES), "rows": rows}


# ============================================================
# B. BFS 路径评测
# ============================================================
# (名称, grid, start, end, 期望可达)
BFS_CASES = [
    ("直线通行", [[0, 0, 0, 0]], (0, 0), (0, 3), True),
    ("中间隔断", [[0, 1, 0]], (0, 0), (0, 2), False),
    ("L 型路径", [[0, 0], [0, 0]], (0, 0), (1, 1), True),
    ("终点被墙包围", [[0, 0, 0], [0, 1, 1], [0, 1, 0]], (0, 0), (2, 2), False),
    ("迷宫可达", [[0, 0, 1, 0], [1, 0, 1, 0], [1, 0, 0, 0], [1, 1, 1, 0]], (0, 0), (3, 3), True),
    ("起点在墙里", [[1, 0], [0, 0]], (0, 0), (1, 1), False),
    ("单格地图", [[0]], (0, 0), (0, 0), True),
    ("双区隔断", [[0, 0, 1, 1, 0], [0, 1, 1, 1, 0], [0, 0, 1, 0, 0]], (0, 0), (2, 4), False),
    ("横向长走廊", [[0] * 10], (0, 0), (0, 9), True),
    ("蛇形路径", [[0, 0, 0], [1, 1, 0], [0, 0, 0]], (0, 0), (2, 0), True),
]


def eval_bfs() -> dict:
    rows, ok_cases = [], 0
    for name, grid, start, end, expect in BFS_CASES:
        r = check_path(grid, start, end)
        ok = r["reachable"] == expect
        ok_cases += 1 if ok else 0
        rows.append({
            "case": name,
            "expect": "可达" if expect else "不可达",
            "actual": "可达" if r["reachable"] else "不可达",
            "pass": ok,
        })
    return {"total": len(BFS_CASES), "passed": ok_cases,
            "rate": ok_cases / len(BFS_CASES), "rows": rows}


# ============================================================
# C. 端到端评测
# ============================================================
E2E_PROMPTS = [
    "制作新手森林关卡，适合 1-3 级玩家，救出村民安娜，哥布林小兵 8 只、首领 1 只，难度偏低。",
    "设计一个洞穴探索关卡，1-3 级，怪物是蝙蝠和岩壳虫，难度偏低。",
    "设计地下城 BOSS 关卡，3-5 级，最终 BOSS 是恶魔领主，难度中等。",
    "设计废墟关卡，2-4 级，主线寻找失落的宝箱，难度偏低。",
    "设计沙漠商队关卡，1-3 级，主线护送商队，难度偏低。",
]


def eval_e2e(n: int) -> dict:
    rows, pass_cnt, bfs_ok = [], 0, 0
    for i, prompt in enumerate(E2E_PROMPTS[:n], 1):
        print(f"  端到端 {i}/{n}: {prompt[:30]}...")
        try:
            state = initial_state(prompt, project_id="eval")
            final = graph.invoke(state, config={"recursion_limit": 50})
            reachable = bool((final.get("map_data") or {}).get("_path_check", {}).get("reachable"))
            status = final.get("review_status")
            retry = final.get("retry_count", 0)
            bfs_ok += 1 if reachable else 0
            pass_cnt += 1 if status == "pass" else 0
            rows.append({
                "prompt": prompt[:40],
                "bfs": "✅" if reachable else "❌",
                "review": status,
                "retry": retry,
                "score": (final.get("review_report") or {}).get("score", "-"),
            })
        except Exception as e:  # noqa: BLE001
            rows.append({"prompt": prompt[:40], "bfs": "ERR", "review": "error",
                         "retry": "-", "score": str(e)[:40]})
    return {"total": len(rows), "bfs_rate": bfs_ok / max(len(rows), 1),
            "pass_rate": pass_cnt / max(len(rows), 1), "rows": rows}


# ============================================================
# 报告
# ============================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--e2e", type=int, default=3)
    ap.add_argument("--skip-e2e", action="store_true")
    args = ap.parse_args()

    print("=" * 60)
    print("A. 数值规则评测")
    num = eval_numeric()
    print(f"  用例 {num['total']} | 通过 {num['passed']} | 准确率 {num['rate']:.0%}")

    print("B. BFS 路径评测")
    bfs = eval_bfs()
    print(f"  用例 {bfs['total']} | 通过 {bfs['passed']} | 准确率 {bfs['rate']:.0%}")

    e2e = None
    if not args.skip_e2e:
        print("C. 端到端评测（每个约 1.5 分钟）")
        e2e = eval_e2e(args.e2e)
        print(f"  BFS 通过率 {e2e['bfs_rate']:.0%} | 评审通过率 {e2e['pass_rate']:.0%}")

    # ---------- 生成报告 ----------
    report_dir = Path("reports")
    report_dir.mkdir(exist_ok=True)
    lines = [
        "# 评测报告",
        "",
        "## A. 数值规则校验（确定性）",
        "",
        f"- 用例数：{num['total']}",
        f"- 通过数：{num['passed']}",
        f"- **准确率：{num['rate']:.0%}**",
        "",
        "| 用例 | 期望 | 实际 | 结果 |",
        "|---|---|---|---|",
    ]
    for r in num["rows"]:
        lines.append(f"| {r['case']} | {r['expect']} | {r['actual']} | {'✅' if r['pass'] else '❌'} |")

    lines += [
        "",
        "## B. BFS 路径校验（确定性）",
        "",
        f"- 用例数：{bfs['total']}",
        f"- 通过数：{bfs['passed']}",
        f"- **准确率：{bfs['rate']:.0%}**",
        "",
        "| 用例 | 期望 | 实际 | 结果 |",
        "|---|---|---|---|",
    ]
    for r in bfs["rows"]:
        lines.append(f"| {r['case']} | {r['expect']} | {r['actual']} | {'✅' if r['pass'] else '❌'} |")

    if e2e:
        lines += [
            "",
            "## C. 端到端流水线（LLM）",
            "",
            f"- 用例数：{e2e['total']}",
            f"- **BFS 通过率：{e2e['bfs_rate']:.0%}**",
            f"- **评审通过率：{e2e['pass_rate']:.0%}**",
            "",
            "| 需求 | BFS | 评审 | 重试 | 评分 |",
            "|---|---|---|---|---|",
        ]
        for r in e2e["rows"]:
            lines.append(f"| {r['prompt']} | {r['bfs']} | {r['review']} | {r['retry']} | {r['score']} |")

    (report_dir / "eval_report.md").write_text("\n".join(lines), encoding="utf-8")
    (report_dir / "eval_data.json").write_text(
        json.dumps({"numeric": num, "bfs": bfs, "e2e": e2e}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n✅ 报告已生成：{report_dir / 'eval_report.md'}")


if __name__ == "__main__":
    main()
