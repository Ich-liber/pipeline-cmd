"""RAG 知识库测试（不需要 LLM Key，只用本地向量模型）。

首次运行会下载 embedding 模型（约 80MB），需要一点时间。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.rag.knowledge_base import KnowledgeBase


def main():
    print("=" * 60)
    print("RAG 知识库测试")
    print("=" * 60)

    kb = KnowledgeBase(persist_dir="data/chroma_test")
    kb.clear()  # 每次测试从干净状态开始

    # ---------- 1. 灌入两条历史设定 ----------
    kb.add_world("req001", {
        "theme": "新手森林",
        "style": "轻松像素风",
        "difficulty": "偏低",
        "player_level_range": "1-3",
        "lore": "森林深处有一个和平的村庄，哥布林首领胆小怕事，只敢在夜里偷袭。",
        "factions": ["村民", "哥布林"],
    })
    kb.add_level("req001", "新手森林", "起始区→战斗区→休息点→首领区→出口，全程步行可达。")
    print("已灌入 2 条历史记录，当前库内数量:", kb.count())

    # ---------- 2. 语义检索 ----------
    queries = [
        "哥布林首领是什么性格",
        "新手森林的难度怎么样",
        "出口怎么走",
    ]
    for q in queries:
        print(f"\n检索: 「{q}」")
        results = kb.search(q, top_k=2)
        for r in results:
            print(f"  [{r['meta'].get('type')}] 距离 {r['distance']:.4f}")
            print(f"    {r['text'][:100]}")

    # ---------- 3. 断言：至少能检索到内容 ----------
    results = kb.search("哥布林首领的性格", top_k=2)
    assert len(results) > 0, "检索结果为空"
    print("\n✅ RAG 知识库测试通过")


if __name__ == "__main__":
    main()
