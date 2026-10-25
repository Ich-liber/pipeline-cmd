"""文档导入（ingest）：把项目已有的世界观/关卡文档批量灌入知识库。

支持格式：
- .md / .txt：整篇作为文档入库
- .json：序列化后入库

目录约定：data/lore/ 下放既有文档，文件名即文档 id。
"""
import json
from pathlib import Path

from app.rag.knowledge_base import KnowledgeBase


def ingest_file(kb: KnowledgeBase, path: Path, project_id: str = "default") -> str:
    """导入单个文件，返回 doc_id。"""
    doc_id = f"lore_{path.stem}"
    if path.suffix.lower() == ".json":
        try:
            content = json.loads(path.read_text(encoding="utf-8"))
            text = json.dumps(content, ensure_ascii=False, indent=2)
        except json.JSONDecodeError:
            text = path.read_text(encoding="utf-8")
        doc_type = "level" if "level" in path.stem.lower() else "world"
    else:
        text = path.read_text(encoding="utf-8")
        doc_type = "level" if "level" in path.stem.lower() else "world"

    kb.add_document(doc_id, text, doc_type, project_id=project_id)
    return doc_id


def ingest_directory(
    lore_dir: str = "data/lore",
    kb: KnowledgeBase | None = None,
    project_id: str = "default",
) -> list[str]:
    """扫描目录，把全部文档灌入知识库。返回已导入的 doc_id 列表。"""
    kb = kb or KnowledgeBase()
    root = Path(lore_dir)
    if not root.exists():
        return []

    docs = []
    for path in sorted(root.iterdir()):
        if path.suffix.lower() in (".md", ".txt", ".json") and path.is_file():
            docs.append(ingest_file(kb, path, project_id=project_id))
    return docs


if __name__ == "__main__":
    kb = KnowledgeBase()
    ids = ingest_directory("data/lore", kb)
    print(f"已导入 {len(ids)} 个文档: {ids}")
    print(f"知识库当前记录数: {kb.count()}")
