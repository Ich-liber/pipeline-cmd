"""PIPELINE·CMD 后端 API（FastAPI）。

前端：web/frontend/index.html（深色战术终端界面）
启动：python -m uvicorn app.api.main:app --host 127.0.0.1 --port 8600
"""
import json
import threading
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.graph import graph
from app.state import initial_state
from app.rag.ingest import ingest_directory
from app.rag.knowledge_base import KnowledgeBase

ROOT = Path(__file__).resolve().parent.parent.parent
FRONTEND = ROOT / "web" / "frontend"

app = FastAPI(title="PIPELINE·CMD")

# 任务表：task_id -> {"status": running|done|error, "result"/"error"}
TASKS: dict[str, dict] = {}


class RunRequest(BaseModel):
    prompt: str
    project: str = "default"


def _serialize(obj):
    """把状态对象转成可 JSON 序列化的结构。"""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items() if not k.startswith("__")}
    if isinstance(obj, (list, tuple)):
        return [_serialize(v) for v in obj]
    return obj


def _run_pipeline(task_id: str, prompt: str, project: str) -> None:
    """在后台线程跑流水线。"""
    try:
        state = initial_state(prompt, project_id=project)
        final = graph.invoke(state, config={"recursion_limit": 50})
        result = _serialize(final)

        # 归档运行记录（树形历史用）
        try:
            kb = KnowledgeBase()
            world = final.get("world_setting") or {}
            title = world.get("theme") or prompt[:24]
            text = (
                f"需求：{prompt}\n\n"
                f"世界观：{json.dumps(world, ensure_ascii=False, indent=2)}\n\n"
                f"评审：{final.get('review_status')}｜评分：{(final.get('review_report') or {}).get('score', '-')}"
            )
            kb.add_run(
                project_id=project,
                request_id=final.get("request_id", ""),
                title=title,
                text=text,
                review_status=final.get("review_status", "pending"),
                payload=result,   # 保存完整产出，供历史详情回放
            )
        except Exception:  # noqa: BLE001
            pass

        TASKS[task_id] = {"status": "done", "result": result}
    except Exception as e:  # noqa: BLE001
        TASKS[task_id] = {"status": "error", "error": str(e)}


@app.post("/api/run")
def run(req: RunRequest):
    """启动一次流水线运行，立即返回 task_id。"""
    if not req.prompt.strip():
        return {"error": "需求为空"}
    task_id = uuid.uuid4().hex[:8]
    TASKS[task_id] = {"status": "running", "started": datetime.now().strftime("%H:%M:%S")}
    threading.Thread(target=_run_pipeline, args=(task_id, req.prompt, req.project), daemon=True).start()
    return {"task_id": task_id}


@app.get("/api/status/{task_id}")
def status(task_id: str):
    return TASKS.get(task_id, {"status": "not_found"})


@app.get("/api/history")
def history(project: str | None = None):
    """返回按项目分组的运行记录（树形）。"""
    kb = KnowledgeBase()
    docs = kb.list_documents()
    runs = [d for d in docs if (d.get("meta") or {}).get("type") == "run"]
    groups: dict[str, list] = {}
    for r in runs:
        meta = r.get("meta") or {}
        p = meta.get("project", "default")
        groups.setdefault(p, []).append({
            "id": r["id"],
            "title": meta.get("title", "未命名"),
            "status": meta.get("review_status", "pending"),
            "time": meta.get("created_at", ""),
            "text": r["text"],
        })
    for items in groups.values():
        items.sort(key=lambda x: x["time"], reverse=True)
    return {"projects": [{"name": k, "runs": v} for k, v in sorted(groups.items())]}


@app.get("/api/run-detail/{run_id}")
def run_detail(run_id: str):
    """返回某条运行记录的完整产出（供历史记录回放）。

    点击历史记录 → 前端拿这份 payload 渲染到 4 个 Tab。
    """
    kb = KnowledgeBase()
    for d in kb.list_documents():
        if d["id"] == run_id:
            payload = (d.get("meta") or {}).get("payload", "")
            if not payload:
                return {"error": "该记录未保存完整产出（旧版本记录，重新运行一次即可回放）"}
            try:
                return json.loads(payload)
            except Exception:  # noqa: BLE001
                return {"error": "产出数据解析失败"}
    return {"error": "记录不存在"}


@app.get("/api/projects")
def projects():
    """列出所有已存在的项目名（供前端下拉选择）。"""
    kb = KnowledgeBase()
    names = kb.projects()
    return {"projects": names or ["default"]}


@app.get("/api/knowledge")
def knowledge():
    kb = KnowledgeBase()
    docs = kb.list_documents()
    others = [d for d in docs if (d.get("meta") or {}).get("type") != "run"]
    return {"docs": [
        {"id": d["id"], "type": (d.get("meta") or {}).get("type", "?"),
         "project": (d.get("meta") or {}).get("project", "-"), "text": d["text"]}
        for d in others
    ]}


@app.post("/api/import")
def import_docs(project: str = "default"):
    kb = KnowledgeBase()
    ids = ingest_directory("data/lore", kb, project_id=project)
    return {"imported": ids, "count": kb.count(project_id=project)}


@app.post("/api/upload")
async def upload_docs(project: str = Form("default"), files: list[UploadFile] = File(...)):
    """接收本地文件上传（.md/.txt/.json），写入知识库。

    适用于：策划在本地写好的世界观文档、地图/关卡描述，直接导入供 Planner 检索。
    """
    kb = KnowledgeBase()
    imported: list[str] = []
    for f in files:
        try:
            content = (await f.read()).decode("utf-8", errors="replace")
            if not content.strip():
                continue
            stem = Path(f.filename or "doc").stem
            doc_id = f"lore_{project}_{stem}"
            doc_type = "level" if "level" in (f.filename or "").lower() or "地图" in (f.filename or "") else "world"
            kb.add_document(doc_id, content, doc_type, project_id=project)
            imported.append(f.filename)
        except Exception:  # noqa: BLE001
            continue
    return {"imported": imported, "count": kb.count(project_id=project)}


@app.get("/")
def index():
    return FileResponse(FRONTEND / "index.html")


# 静态资源（如有）
if FRONTEND.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND), name="static")
