"""全局状态定义（LangGraph State）。

用 TypedDict 定义，LangGraph 的节点函数接收并返回这个字典的增量更新。
字段与需求文档「五、数据结构设计」对齐。
"""
from typing import TypedDict, Literal, Any


class GamePlanState(TypedDict, total=False):
    # ---------- 输入 ----------
    request_id: str                 # 本次请求 ID
    project_id: str                 # 项目/游戏 ID（同一游戏共享世界观）
    user_raw_prompt: str            # 用户原始自然语言需求

    # ---------- 各 Agent 产出 ----------
    world_setting: dict             # PlannerAgent：世界观总设定
    task_list: list                 # PlannerAgent：任务拆解清单
    map_data: dict                  # MapAgent：Tiled 兼容地图 JSON
    dialogue_data: dict             # DialogueAgent：NPC 对话树 JSON
    monster_numeric_data: dict      # ValidatorAgent 读取/修正的怪物数值
    validate_report: dict           # NumericValidatorAgent：校验报告
    review_report: dict             # ReviewAgent：综合评审报告

    # ---------- 流程控制 ----------
    review_status: Literal["pending", "pass", "reject"]   # 评审结论
    human_modify: bool              # 是否人工介入修改过
    error_log: list                 # 错误日志
    version_tag: str                # 版本标签
    current_stage: str              # 当前所处阶段（planner/map/dialogue/validate/review）
    retry_count: int                # 已重试轮次（防无限循环）


def initial_state(user_prompt: str, project_id: str = "default") -> GamePlanState:
    """构造初始状态。

    project_id: 项目/游戏标识，同一游戏的多条需求共享同一 project_id，
                知识库检索与世界观沉淀都按它隔离。
    """
    import uuid

    return GamePlanState(
        request_id=uuid.uuid4().hex[:8],
        project_id=project_id,
        user_raw_prompt=user_prompt,
        world_setting={},
        task_list=[],
        map_data={},
        dialogue_data={},
        monster_numeric_data={},
        validate_report={},
        review_report={},
        review_status="pending",
        human_modify=False,
        error_log=[],
        version_tag="v1",
        current_stage="planner",
        retry_count=0,
    )
