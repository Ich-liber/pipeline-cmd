"""完整 RAG 闭环测试：
1. 导入既有文档（data/lore）
2. Planner 处理新需求（会检索既有文档）
3. 验证：检索到 + 遵守设定
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agents.planner import run_planner
from app.rag.ingest import ingest_directory
from app.rag.knowledge_base import KnowledgeBase
from app.state import initial_state


def main():
    print("=" * 60)
    print("完整 RAG 闭环：既有文档 → Planner → 遵守设定")
    print("=" * 60)

    # 1. 清空并导入既有文档
    kb = KnowledgeBase()
    kb.clear()
    ids = ingest_directory("data/lore", kb)
    print(f"已导入既有文档: {ids}（含「哥布林首领胆小」设定）")

    # 2. 新需求：故意要求哥布林首领当 BOSS
    prompt = "设计一个哥布林巢穴副本，哥布林首领作为最终 BOSS，难度中等。"
    print(f"\n新需求: {prompt}")

    # 3. 跑 Planner（内部会 RAG 检索）
    state = initial_state(prompt)
    result = run_planner(state)

    print("\n【Planner 日志】")
    for e in result.get("error_log", []):
        print("  -", e)

    print("\n【生成的世界观】")
    print(json.dumps(result.get("world_setting", {}), ensure_ascii=False, indent=2))

    # 4. 断言
    logs = "\n".join(result.get("error_log", []))
    assert "RAG 检索到" in logs, "❌ 没有检索到既有文档"
    print("\n✅ 验证通过：Planner 检索到了既有文档")
    print("👀 人工检查：lore 里是否体现了「胆小」这个人设（而非勇猛战士）")


if __name__ == "__main__":
    main()
