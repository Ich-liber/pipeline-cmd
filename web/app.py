r"""游戏关卡 & 剧情策划辅助多智能体系统 —— Streamlit 演示界面。

启动：
    cd game-agent
    .venv\Scripts\streamlit run web/app.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import streamlit as st

from app.graph import graph
from app.state import initial_state
from app.rag.ingest import ingest_directory
from app.rag.knowledge_base import KnowledgeBase
import json

st.set_page_config(
    page_title="游戏策划多智能体系统",
    page_icon="🎮",
    layout="wide",
)


@st.cache_resource
def get_kb() -> KnowledgeBase:
    """缓存知识库实例（Chroma 持久化客户端只创建一次）。"""
    return KnowledgeBase()


DEMO_PROMPT = (
    "制作新手森林关卡，适合 1-3 级玩家，主线任务：救出森林里的村民安娜；"
    "怪物：哥布林小兵 8 只、哥布林首领 1 只；奖励：草药、少量铜币；"
    "难度偏低，路线简单，设置一个安全休息点。"
)

# ============================================================
# 全局样式
# ============================================================
st.markdown(
    """
    <style>
      .block-container { padding-top: 1.4rem; max-width: 1400px; }
      h1 { letter-spacing: -0.5px; }
      .stTabs [data-baseweb="tab-list"] { gap: 6px; }
      .stTabs [data-baseweb="tab"] { border-radius: 8px 8px 0 0; padding: 8px 16px; }

      .card {
        background: #FFFFFF;
        border: 1px solid #DDD6FE;
        border-radius: 14px;
        padding: 16px 20px;
        margin-bottom: 14px;
      }
      .card h4 { margin: 0 0 10px 0; font-size: 0.95rem; color: #6D28D9; }
      .kv { display: flex; gap: 8px; margin: 6px 0; }
      .kv .k { color: #6B7280; min-width: 92px; font-size: 0.88rem; }
      .kv .v { color: #1E1B4B; font-size: 0.92rem; }
      .tag {
        display: inline-block; padding: 2px 10px; border-radius: 999px;
        background: #EDE9FE; color: #6D28D9; font-size: 0.8rem; margin: 2px 4px 2px 0;
      }
      .lore {
        background: #FAF5FF; border-left: 3px solid #7C3AED;
        padding: 12px 16px; border-radius: 0 10px 10px 0;
        font-size: 0.94rem; line-height: 1.8; color: #1E1B4B;
      }
      .verdict-pass {
        background: #ECFDF5; border: 1px solid #10B981; color: #047857;
        border-radius: 12px; padding: 14px 20px; font-size: 1.05rem; font-weight: 600;
        margin-bottom: 12px;
      }
      .verdict-reject {
        background: #FEF2F2; border: 1px solid #EF4444; color: #B91C1C;
        border-radius: 12px; padding: 14px 20px; font-size: 1.05rem; font-weight: 600;
        margin-bottom: 12px;
      }
      .issue-block { color: #B91C1C; }
      .issue-warn { color: #B45309; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# 顶部
# ============================================================
st.title("🎮 游戏关卡 & 剧情策划辅助")
st.caption("多智能体流水线 · Planner → Map → Dialogue → Validator → Review")

# ============================================================
# 侧边栏
# ============================================================
if "prompt_area" not in st.session_state:
    st.session_state["prompt_area"] = ""


def fill_demo():
    st.session_state["prompt_area"] = DEMO_PROMPT


if "project" not in st.session_state:
    st.session_state["project"] = "default"

with st.sidebar:
    st.header("① 策划需求")
    project = st.text_input(
        "项目 / 游戏名称",
        key="project",
        help="同一游戏的多条需求用同一个项目名；知识库按项目隔离，避免不同游戏串味",
    )
    st.text_area(
        "用自然语言描述你的关卡需求",
        height=180,
        placeholder="例如：制作新手森林关卡，适合 1-3 级玩家…",
        key="prompt_area",
    )
    c1, c2 = st.columns(2)
    with c1:
        st.button("填入示例", use_container_width=True, on_click=fill_demo)
    with c2:
        run_btn = st.button("🚀 运行", type="primary", use_container_width=True)

    st.divider()
    st.header("② 知识库")
    st.caption("导入 data/lore 下的既有设定文档，供 Planner 检索防冲突")
    if st.button("导入既有文档", use_container_width=True):
        try:
            kb = get_kb()
            ids = ingest_directory("data/lore", kb, project_id=project)
            if ids:
                st.success(f"导入 {len(ids)} 个：{'、'.join(ids)}")
            else:
                st.warning("data/lore 下没有可导入的文档")
            st.info(f"项目「{project}」当前共 {kb.count(project_id=project)} 条记录")
        except Exception as e:  # noqa: BLE001
            st.error(f"导入失败：{e}")

    st.divider()
    st.caption("🧠 LLM：DeepSeek｜流水线：LangGraph")
    st.caption("📦 数据：Chroma 向量库 + 轻量语义检索")


# ============================================================
# 渲染函数
# ============================================================
def render_world(world: dict):
    """世界观卡片。"""
    if not world:
        st.caption("本次没有生成世界观")
        return
    factions = "".join(f'<span class="tag">{f}</span>' for f in (world.get("factions") or []))
    st.markdown(
        f"""
        <div class="card">
          <h4>🌍 {world.get("theme", "未命名世界观")}</h4>
          <div class="kv"><span class="k">风格</span><span class="v">{world.get("style", "-")}</span></div>
          <div class="kv"><span class="k">难度</span><span class="v">{world.get("difficulty", "-")}</span></div>
          <div class="kv"><span class="k">玩家等级</span><span class="v">{world.get("player_level_range", "-")}</span></div>
          <div class="kv"><span class="k">阵营</span><span class="v">{factions or '-'}</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if world.get("lore"):
        st.markdown('<div class="lore">' + world["lore"] + "</div>", unsafe_allow_html=True)


def render_map(map_data: dict):
    """地图可视化（HTML 网格）+ 路径校验。"""
    if not map_data:
        st.caption("本次没有生成地图")
        return

    grid = map_data.get("grid") or []
    start = map_data.get("_start_rc")   # (row, col)，由 MapAgent 转换
    end = map_data.get("_end_rc")
    check = map_data.get("_path_check") or {}

    # 路径校验状态
    if check.get("reachable"):
        st.success(f"✅ 路径校验通过：{check.get('message')}")
    elif check:
        st.error(f"❌ 路径校验失败：{check.get('message')}")

    # 地图网格可视化
    if grid:
        cell = 15
        html = [
            f"<div style='display:grid;grid-template-columns:repeat({len(grid[0])},{cell}px);"
            "gap:2px;background:#EEE9FF;padding:8px;border-radius:10px;width:fit-content'>"
        ]
        for r, row in enumerate(grid):
            for c, v in enumerate(row):
                color = "#EDE9FE"  # 地面
                if v == 1:
                    color = "#312E81"  # 墙
                if start and [r, c] == list(start):
                    color = "#0891B2"  # 起点：青
                if end and [r, c] == list(end):
                    color = "#7C3AED"  # 终点：紫
                html.append(
                    f"<div title='({r},{c})' style='width:{cell}px;height:{cell}px;"
                    f"background:{color};border-radius:2px'></div>"
                )
        html.append("</div>")
        st.markdown("".join(html), unsafe_allow_html=True)
        st.caption("🟦 起点　🟪 终点　⬛ 障碍　⬜ 可通行")

    # 刷点 / 资源
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**怪物刷点**")
        spawns = map_data.get("spawn_points") or []
        if spawns:
            for s in spawns:
                st.markdown(f"- ({s.get('x')},{s.get('y')}) {s.get('monster')} × {s.get('count')}")
        else:
            st.caption("无")
    with col_b:
        st.markdown("**资源点**")
        res = map_data.get("resource_points") or []
        if res:
            for r in res:
                st.markdown(f"- ({r.get('x')},{r.get('y')}) {r.get('type')}")
        else:
            st.caption("无")

    if map_data.get("description"):
        st.caption(map_data["description"])


def render_dialogue(dialogue_data: dict):
    """NPC 对话树。"""
    npcs = (dialogue_data or {}).get("npcs") or []
    if not npcs:
        st.caption("本次没有生成对话")
        return

    for npc in npcs:
        st.markdown(
            f"""
            <div class="card">
              <h4>💬 {npc.get("name", "NPC")}　<span class="tag">{npc.get("role", "")}</span></h4>
              <div class="kv"><span class="k">人设</span><span class="v">{npc.get("personality", "-")}</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        for d in npc.get("dialogues") or []:
            options = d.get("options") or []
            cond = d.get("conditions") or {}
            cond_text = ""
            if cond:
                cond_text = "　" + "".join(f"<span class='tag'>{k}:{v}</span>" for k, v in cond.items())
            st.markdown(
                f"**{npc.get('name', 'NPC')}**：{d.get('text', '')}"
                f"　<span style='color:#9CA3AF;font-size:0.76rem'>#{d.get('id', '?')}</span>{cond_text}",
                unsafe_allow_html=True,
            )
            for opt in options:
                st.markdown(f"　　↳ 选项：{opt.get('text')} → `{opt.get('next')}`")


def render_numeric(numeric_data: dict, validate_report: dict):
    """数值表 + 校验结果。"""
    monsters = (numeric_data or {}).get("monsters") or []
    if monsters:
        rows = []
        for m in monsters:
            drops = m.get("drops") or []
            drop_text = "、".join(f"{d.get('item')}({d.get('rate')}%)" for d in drops) or "-"
            rows.append({
                "ID": m.get("id"),
                "名称": m.get("name"),
                "血量": m.get("hp"),
                "攻击": m.get("attack"),
                "防御": m.get("defense"),
                "金币": m.get("gold"),
                "掉落": drop_text,
            })
        try:
            import pandas as pd

            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        except Exception:  # noqa: BLE001
            st.table(rows)
    else:
        st.caption("本次没有生成怪物数值")

    # 校验结果
    issues = (validate_report or {}).get("issues") or []
    if issues:
        st.markdown("**校验发现的问题**")
        for it in issues:
            cls = "issue-block" if it.get("level") == "block" else "issue-warn"
            icon = "⛔" if it.get("level") == "block" else "⚠️"
            st.markdown(
                f"<span class='{cls}'>{icon} [{it.get('monster_name', '')}] {it.get('message', '')}</span>"
                f"　→ <span style='color:#6B7280'>{it.get('suggest', '')}</span>",
                unsafe_allow_html=True,
            )
    elif validate_report:
        st.success("✅ 数值校验全部通过")

    if (numeric_data or {}).get("difficulty_note"):
        st.caption("难度说明：" + numeric_data["difficulty_note"])


def render_review(review_report: dict, status: str):
    """评审报告。"""
    if not review_report:
        st.caption("本次没有评审报告")
        return

    if status == "pass":
        st.markdown('<div class="verdict-pass">✅ 评审通过</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="verdict-reject">⛔ 评审驳回</div>', unsafe_allow_html=True)

    score = review_report.get("score")
    if score is not None:
        st.metric("综合评分", f"{score} / 100")

    issues = review_report.get("issues") or []
    if issues:
        st.markdown("**问题清单**")
        for it in issues:
            cls = "issue-block" if it.get("level") == "block" else "issue-warn"
            icon = "⛔" if it.get("level") == "block" else "⚠️"
            st.markdown(
                f"<span class='{cls}'>{icon} [{it.get('part', '')}] {it.get('message', '')}</span>",
                unsafe_allow_html=True,
            )

    suggestions = review_report.get("suggestions") or []
    if suggestions:
        st.markdown("**修改建议**")
        for s in suggestions:
            st.markdown(f"- {s}")

    if review_report.get("summary"):
        st.caption("总结：" + review_report["summary"])


# ============================================================
# 运行
# ============================================================
if run_btn:
    if not st.session_state["prompt_area"].strip():
        st.error("请先在左侧输入策划需求")
    else:
        try:
            with st.spinner("流水线运行中：规划 → 地图 → 对话 → 校验 → 评审（约 1–2 分钟）…"):
                state = initial_state(
                    st.session_state["prompt_area"],
                    project_id=st.session_state.get("project", "default"),
                )
                final = graph.invoke(state, config={"recursion_limit": 50})
            st.session_state["result"] = final

            # 归档本次运行（带总结标题，供树形历史展示）
            try:
                _project = st.session_state.get("project", "default")
                _world = final.get("world_setting") or {}
                _title = _world.get("theme") or st.session_state["prompt_area"][:24]
                _text = (
                    f"需求：{st.session_state['prompt_area']}\n\n"
                    f"世界观：{json.dumps(_world, ensure_ascii=False, indent=2)}\n\n"
                    f"评审结论：{final.get('review_status')}\n"
                    f"评分：{(final.get('review_report') or {}).get('score', '-')}"
                )
                get_kb().add_run(
                    project_id=_project,
                    request_id=final.get("request_id", ""),
                    title=_title,
                    text=_text,
                    review_status=final.get("review_status", "pending"),
                )
            except Exception:  # noqa: BLE001
                pass
        except Exception as e:  # noqa: BLE001
            st.error(f"运行失败：{e}")

# ============================================================
# 结果
# ============================================================
if "result" in st.session_state:
    final = st.session_state["result"]
    status = final.get("review_status", "pending")

    # 结论条
    if status == "pass":
        st.markdown('<div class="verdict-pass">✅ 评审通过</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="verdict-reject">⛔ 评审驳回（可修改需求后重新运行）</div>', unsafe_allow_html=True)

    # 概览指标
    vr = final.get("validate_report", {})
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("数值阻断", vr.get("block_count", 0))
    m2.metric("数值警告", vr.get("warning_count", 0))
    m3.metric("NPC 数", len(final.get("dialogue_data", {}).get("npcs", [])))
    m4.metric("重试轮次", final.get("retry_count", 0))

    # 详情 tabs（可读 UI）
    tabs = st.tabs(["🌍 世界观", "🗺️ 地图", "💬 对话", "⚔️ 数值", "📋 评审报告", "📜 日志"])

    with tabs[0]:
        render_world(final.get("world_setting", {}))
    with tabs[1]:
        render_map(final.get("map_data", {}))
    with tabs[2]:
        render_dialogue(final.get("dialogue_data", {}))
    with tabs[3]:
        render_numeric(final.get("monster_numeric_data", {}), final.get("validate_report", {}))
    with tabs[4]:
        render_review(final.get("review_report", {}), status)
    with tabs[5]:
        logs = final.get("error_log", [])
        if logs:
            for e in logs:
                st.code(e)
        else:
            st.caption("无日志")

    # 原始 JSON（折叠）
    with st.expander("🔧 查看原始 JSON（开发者视图）"):
        st.json(final)
else:
    st.info("👈 在左侧输入策划需求，然后点击「运行」开始。")
    with st.expander("系统能做什么？"):
        st.markdown(
            """
            - **规划**：解析需求，生成世界观与任务清单
            - **地图**：生成关卡布局，BFS 校验可达性
            - **对话**：生成 NPC 分支对话树
            - **数值**：生成怪物数值，硬规则校验（防秒杀/爆率/通胀）
            - **评审**：综合评审，通过或驳回迭代
            - **RAG**：检索历史设定，防止世界观冲突
            """
        )

# ============================================================
# 知识库浏览
# ============================================================
st.markdown("---")
_kb = get_kb()
_all_docs = _kb.list_documents()
_current_project = st.session_state.get("project", "default")

st.subheader("📚 历史记录与知识库")

_runs = [d for d in _all_docs if (d.get("meta") or {}).get("type") == "run"]
_others = [d for d in _all_docs if (d.get("meta") or {}).get("type") != "run"]

# ---------- 运行记录：按项目分组的树形 ----------
if not _runs:
    st.caption("还没有运行记录。运行一次流水线后，这里会按项目归档（像会话列表一样）。")
else:
    import html as _html

    _groups = {}
    for _r in _runs:
        _p = (_r.get("meta") or {}).get("project", "default")
        _groups.setdefault(_p, []).append(_r)

    _parts = []
    for _project, _items in sorted(_groups.items()):
        _items.sort(key=lambda x: (x.get("meta") or {}).get("created_at", ""), reverse=True)
        _opened = " open" if _project == _current_project else ""
        _parts.append(
            f"<details{_opened} style='margin-bottom:10px;border:1px solid #DDD6FE;border-radius:10px;"
            "padding:8px 12px;background:#fff'>"
            f"<summary style='cursor:pointer;font-weight:600;color:#6D28D9'>📁 {_html.escape(_project)}"
            f"<span style='color:#9CA3AF;font-weight:400;font-size:0.85rem'>（{len(_items)} 次运行）</span></summary>"
        )
        for _it in _items:
            _meta = _it.get("meta") or {}
            _status = _meta.get("review_status", "")
            _icon = "✅" if _status == "pass" else "⛔"
            _title = _html.escape(str(_meta.get("title", "未命名")))
            _time = _meta.get("created_at", "")
            _body = _html.escape(_it.get("text", ""))
            _parts.append(
                "<details style='margin:6px 0 6px 14px'>"
                f"<summary style='cursor:pointer;font-size:0.9rem'>{_icon} {_title}"
                f"<span style='color:#9CA3AF;font-size:0.8rem'>　{_time}</span></summary>"
                "<pre style='font-size:0.78rem;white-space:pre-wrap;background:#FAF5FF;"
                f"padding:10px;border-radius:8px;margin-top:6px'>{_body}</pre></details>"
            )
        _parts.append("</details>")
    st.markdown("".join(_parts), unsafe_allow_html=True)

# ---------- 其他文档（世界观 / 导入设定） ----------
if _others:
    st.markdown(f"**📄 其他文档（{len(_others)} 条：世界观 / 导入设定）**")
    for _doc in _others:
        _meta = _doc.get("meta") or {}
        _label = (
            f"{_doc['id']}　·　{_meta.get('type', '?')}"
            f"　·　项目:{_meta.get('project', '-')}"
        )
        with st.expander(_label):
            st.text(_doc.get("text", ""))
