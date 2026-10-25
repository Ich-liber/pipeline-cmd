"""RAG 知识库模块。

定位（需求文档 3.8）：
- 存储历史世界观文档、旧关卡配置；
- 供 Planner 在生成前检索，保证前后设定统一；
- RAG 只做上下文检索，不做主生成。

多项目支持：
- 每条记录带 project 元数据（游戏/项目 ID）；
- 同一项目的世界观覆盖更新（world_<project>），避免碎片化；
- 检索优先按项目过滤，查不到再回退全局。

实现说明：
- 向量库：Chroma（本地持久化，存 data/chroma 目录）
- Embedding：SimpleHashEmbedding（字符 n-gram 哈希，零依赖、离线可用）
"""
import json

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.rag.embedding import SimpleHashEmbedding


class KnowledgeBase:
    """世界观/旧关卡知识库。"""

    def __init__(self, persist_dir: str = "data/chroma"):
        self._embedding = SimpleHashEmbedding()
        self.client = chromadb.PersistentClient(
            path=persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_or_create_collection(
            name="world_lore",
            metadata={"hnsw:space": "cosine"},
            embedding_function=self._embedding,
        )

    # ---------- 写入 ----------
    def add_world(
        self,
        request_id: str,
        world_setting: dict,
        summary: str = "",
        project_id: str = "default",
    ) -> str:
        """写入/更新某个项目的世界观。

        同一项目只保留一份最新世界观（doc_id = world_<project>），
        避免多条需求把世界观碎片化成多条记录。
        """
        text = summary or self._world_to_text(world_setting)
        doc_id = f"world_{project_id}"
        self.collection.upsert(
            documents=[text],
            metadatas=[{"type": "world", "request_id": request_id, "project": project_id}],
            ids=[doc_id],
        )
        return doc_id

    def add_level(
        self,
        request_id: str,
        level_name: str,
        description: str,
        project_id: str = "default",
    ) -> str:
        """写入一条关卡产出记录（按需求归档，可追溯）。"""
        doc_id = f"level_{project_id}_{request_id}"
        self.collection.upsert(
            documents=[f"关卡：{level_name}\n{description}"],
            metadatas=[{"type": "level", "request_id": request_id, "project": project_id}],
            ids=[doc_id],
        )
        return doc_id

    def add_document(
        self,
        doc_id: str,
        text: str,
        doc_type: str = "world",
        project_id: str = "default",
    ) -> str:
        """通用文档入库（用于导入项目已有的世界观/关卡文档）。"""
        self.collection.upsert(
            documents=[text],
            metadatas=[{"type": doc_type, "source": "import", "project": project_id}],
            ids=[doc_id],
        )
        return doc_id

    def add_run(
        self,
        project_id: str,
        request_id: str,
        title: str,
        text: str,
        review_status: str = "pending",
        payload: dict | None = None,
    ) -> str:
        """归档一次运行记录（带总结标题与完整产出，供界面树形展示与详情回放）。"""
        from datetime import datetime

        doc_id = f"run_{project_id}_{request_id}"
        self.collection.upsert(
            documents=[text],
            metadatas=[{
                "type": "run",
                "project": project_id,
                "request_id": request_id,
                "title": title,
                "review_status": review_status,
                "created_at": datetime.now().strftime("%m-%d %H:%M"),
                "source": "generated",
                "payload": json.dumps(payload, ensure_ascii=False) if payload else "",
            }],
            ids=[doc_id],
        )
        return doc_id

    # ---------- 检索 ----------
    def search(
        self,
        query: str,
        top_k: int = 3,
        project_id: str | None = None,
        exclude_types: tuple = ("run",),
    ) -> list[dict]:
        """语义检索相关设定，用于 Planner 生成前的上下文注入。

        规则：
        - 严格按 project_id 隔离（不跨项目）；
        - 默认排除 run（历史运行归档），只检索用户上传文档（lore）与项目世界观（world）；
        - 多取候选再过滤，保证过滤后仍有 top_k 条。

        返回: [{"text": ..., "meta": {...}, "distance": ...}]
        """
        total = self.collection.count()
        if total == 0:
            return []

        def _query(where, n):
            kwargs = {
                "query_texts": [query],
                "n_results": min(n, total),
            }
            if where:
                kwargs["where"] = where
            res = self.collection.query(**kwargs)
            docs = res.get("documents", [[]])[0]
            metas = res.get("metadatas", [[]])[0]
            dists = res.get("distances", [[]])[0]
            return [
                {"text": d, "meta": m, "distance": dist}
                for d, m, dist in zip(docs, metas, dists)
            ]

        # 严格按项目隔离：指定项目时只查本项目，不跨项目回退
        where = {"project": project_id} if project_id else None
        raw = _query(where, top_k * 4 + 4)
        filtered = [
            r for r in raw
            if (r.get("meta") or {}).get("type") not in exclude_types
        ]
        return filtered[:top_k]

    def count(self, project_id: str | None = None) -> int:
        if not project_id:
            return self.collection.count()
        try:
            res_all = self.collection.get(where={"project": project_id})
            return len(res_all.get("ids", []) or [])
        except Exception:  # noqa: BLE001
            return 0

    def list_documents(self, limit: int = 200, project_id: str | None = None) -> list[dict]:
        """列出知识库文档（可按项目过滤，用于界面浏览）。"""
        kwargs = {"limit": limit}
        if project_id:
            kwargs["where"] = {"project": project_id}
        res = self.collection.get(**kwargs)
        ids = res.get("ids", []) or []
        docs = res.get("documents", []) or []
        metas = res.get("metadatas", []) or []
        return [
            {"id": i, "text": d, "meta": m or {}}
            for i, d, m in zip(ids, docs, metas)
        ]

    def projects(self) -> list[str]:
        """列出知识库中出现过的所有项目 ID。"""
        res = self.collection.get(limit=500)
        metas = res.get("metadatas", []) or []
        return sorted({str(m.get("project", "default")) for m in metas if m})

    def clear(self) -> None:
        """清空知识库（测试用）。"""
        try:
            self.client.delete_collection("world_lore")
        except Exception:  # noqa: BLE001
            pass
        self.collection = self.client.get_or_create_collection(
            name="world_lore",
            metadata={"hnsw:space": "cosine"},
            embedding_function=self._embedding,
        )

    # ---------- 工具 ----------
    @staticmethod
    def _world_to_text(world: dict) -> str:
        """把世界观 dict 转成适合检索的自然语言文本。"""
        parts = ["世界观设定："]
        for key in ("theme", "style", "difficulty", "player_level_range", "lore"):
            if world.get(key):
                parts.append(f"{key}: {world[key]}")
        if world.get("factions"):
            parts.append("factions: " + "、".join(world["factions"]))
        return "\n".join(parts)
