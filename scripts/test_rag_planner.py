"""测试：RAG 是否接入 Planner。

步骤：
1. 灌入历史设定（哥布林首领胆小怕事）
2. 新需求故意提到哥布林首领
3. 看 Planner 是否检索到历史、生成结果是否与历史一致
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agents.planner import run_planner
from app.rag.knowledge_base import KnowledgeBase
from app.state import initial_state


def main():
    print("=" * 60)
    print("测试：RAG 接入 Planner")
    print("=" * 60)

    # ---------- 1. 准备历史设定 ----------
    kb = KnowledgeBase(persist_dir="data/chroma")
    kb.clear()
    kb.add_world("history_001", {
        "theme": "新手森林",
        "style": "轻松像素风",
        "lore": "森林深处有一个和平的村庄。哥布林首领胆小怕事，只敢在夜里偷袭，从不敢正面战斗。",
        "factions": ["村民", "哥布林"],
    })
    print("已灌入历史设定：哥布林首领「胆小怕事，只敢夜里偷袭」")
    print("知识库记录数:", kb.count())

    # ---------- 2. 新需求（故意提到哥布林首领） ----------
    prompt = "设计一个哥布林巢穴副本，需要哥布林首领作为最终 BOSS，难度中等，偏紧张刺激。"
    print("\n新需求:", prompt)

    # ---------- 3. 跑 Planner ----------
    state = initial_state(prompt)
    result = run_planner(state)

    print("\n【Planner 日志】")
    for e in result.get("error_log", []):
        print("  -", e)

    print("\n【生成的世界观】")
    print(json.dumps(result.get("world_setting", {}), ensure_ascii=False, indent=2))

    # ---------- 4. 断言 ----------
    logs = "\n".join(result.get("error_log", []))
    assert "RAG 检索到" in logs, "❌ Planner 没有走 RAG 检索"
    print("\n✅ RAG 已接入 Planner（日志中有检索记录）")
    print("👀 请人工检查：生成的世界观里，哥布林首领是否和「胆小怕事」的历史设定冲突？")


if __name__ == "__main__":
    main()
