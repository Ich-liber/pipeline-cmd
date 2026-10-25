"""测试：文档导入（既有文档 → 知识库 → 检索）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.rag.knowledge_base import KnowledgeBase
from app.rag.ingest import ingest_directory


def main():
    print("=" * 60)
    print("测试：既有文档导入 + 检索")
    print("=" * 60)

    kb = KnowledgeBase()
    kb.clear()
    print("知识库已清空")

    ids = ingest_directory("data/lore", kb)
    print(f"已导入 {len(ids)} 个文档: {ids}")
    print(f"知识库记录数: {kb.count()}")
    assert len(ids) > 0, "没有导入任何文档"

    queries = [
        "哥布林首领是什么性格",
        "新手森林的难度怎么样",
        "地图能不能通行",
        "安娜是谁",
    ]
    for q in queries:
        print(f"\n检索: 「{q}」")
        results = kb.search(q, top_k=2)
        for r in results:
            text = r["text"][:70].replace("\n", " ")
            print(f"  [{r['meta'].get('type')}] 距离 {r['distance']:.4f} | {text}")
        assert len(results) > 0, f"「{q}」检索为空"

    # 关键验证：必须能检索到"哥布林首领胆小"这个既有设定
    hits = kb.search("哥布林首领的性格", top_k=1)
    assert hits and "胆小" in hits[0]["text"], "未命中哥布林首领的胆小设定"
    print("\n✅ 文档导入验证通过：能检索到既有文档中的设定")


if __name__ == "__main__":
    main()
