import json
from pathlib import Path

import streamlit as st

from backend.coach import run_coach
from backend.history_service import append_run
from backend.workflow_trace import (
    all_project_resources,
    expand_source_patterns,
    legacy_workflow_from_result,
    read_project_file,
)


STATUS = {
    "success": ("●", "完成"),
    "blocked": ("◆", "已拦截"),
    "error": ("×", "失败"),
    "skipped": ("○", "已跳过"),
    "running": ("◉", "运行中"),
    "pending": ("·", "未运行"),
}


def inject_workflow_css():
    st.markdown("""
    <style>
      .stApp { background: #f6f8fb; color: #172033; }
      .block-container { max-width: 100%; padding: 1.2rem 1.5rem 2rem; }
      h1, h2, h3 { letter-spacing: -0.025em; }
      [data-testid="stHeader"] { background: rgba(246,248,251,.88); }
      .studio-kicker { color:#2563eb; font-size:.76rem; font-weight:700; letter-spacing:.1em; text-transform:uppercase; }
      .studio-title { font-size:1.72rem; line-height:1.15; font-weight:760; margin:.15rem 0 .25rem; color:#121a2b; }
      .studio-subtitle { color:#667085; font-size:.9rem; margin-bottom:1rem; }
      .panel-label { color:#667085; font-size:.72rem; font-weight:750; letter-spacing:.08em; text-transform:uppercase; margin:.25rem 0 .7rem; }
      .flow-meta { background:#eef4ff; color:#1d4ed8; border-radius:8px; padding:.55rem .7rem; font-size:.78rem; margin-bottom:.7rem; }
      .flow-arrow { text-align:center; color:#a7b0c0; height:18px; line-height:18px; font-size:15px; }
      .answer-box { border-left:3px solid #2563eb; padding:.25rem 0 .25rem .85rem; margin:.7rem 0 1rem; color:#273247; }
      .node-description { color:#667085; font-size:.78rem; line-height:1.45; margin:-.2rem 0 .55rem; }
      .status-line { color:#667085; font-size:.76rem; margin:.2rem 0 .65rem; }
      .source-path { color:#475467; font-family:ui-monospace,SFMono-Regular,Consolas,monospace; font-size:.75rem; }
      div[data-testid="stVerticalBlockBorderWrapper"] { background:#fff; border-color:#e4e8ef; border-radius:12px; }
      div.stButton > button { width:100%; text-align:left; justify-content:flex-start; border:1px solid #dde3ec; background:#fff; color:#273247; min-height:2.65rem; border-radius:9px; font-weight:620; }
      div.stButton > button:hover { border-color:#7aa2f7; color:#1749a8; background:#f8fbff; }
      button[data-testid="stBaseButton-primary"], button[data-testid="stBaseButton-primaryFormSubmit"] { background:#2563eb !important; border-color:#2563eb !important; color:#fff !important; justify-content:center !important; }
      button[data-testid="stBaseButton-primary"]:hover, button[data-testid="stBaseButton-primaryFormSubmit"]:hover { background:#1d4ed8 !important; border-color:#1d4ed8 !important; }
      div[data-testid="stForm"] { border:0; padding:0; }
      [data-testid="stTabs"] [data-baseweb="tab-list"] { gap:.35rem; }
      [data-testid="stTabs"] button[role="tab"] { height:2.5rem; padding:0 .75rem; }
      [data-testid="stMetric"] { background:#fff; border:1px solid #e4e8ef; padding:.65rem .75rem; border-radius:10px; }
      code { font-size:.78rem !important; }
    </style>
    """, unsafe_allow_html=True)


def _set_selected_node(node_id):
    st.session_state["selected_node_id"] = node_id
    st.session_state.pop("selected_source_file", None)


def render_catalog():
    st.markdown('<div class="panel-label">模块与文件</div>', unsafe_allow_html=True)
    search = st.text_input(
        "搜索文件",
        key="resource_search",
        placeholder="router.py / rubric / P07",
        label_visibility="collapsed",
    ).strip().lower()
    for group in all_project_resources():
        files = group["resolved_files"]
        if search:
            files = [path for path in files if search in path.lower()]
        if not files:
            continue
        with st.expander(f'{group["title"]}  ·  {len(files)}', expanded=bool(search)):
            for relative_path in files:
                label = Path(relative_path).name
                if st.button(label, key=f"resource::{group['id']}::{relative_path}", help=relative_path):
                    st.session_state["selected_source_file"] = relative_path
                    st.session_state["inspector_mode"] = "source"


def render_workflow(result):
    st.markdown('<div class="panel-label">本次执行链路</div>', unsafe_allow_html=True)
    if not result:
        st.info("在右侧发送问题后，这里会显示实际执行的完整节点链路。")
        return

    workflow = legacy_workflow_from_result(result)
    routing = ((result.get("trace") or {}).get("routing") or {}).get("parsed") or {}
    prototype = routing.get("prototype", "—")
    duration = workflow.get("duration_ms")
    duration_text = f"{duration / 1000:.2f}s" if isinstance(duration, (int, float)) else "旧版记录"
    st.markdown(
        f'<div class="flow-meta">Prototype <b>{prototype}</b> · '
        f'{len(workflow.get("nodes", []))} nodes · {duration_text}</div>',
        unsafe_allow_html=True,
    )

    selected = st.session_state.get("selected_node_id")
    if not selected and workflow.get("nodes"):
        selected = next(
            (node["id"] for node in workflow["nodes"] if node["status"] not in {"skipped", "pending"}),
            workflow["nodes"][0]["id"],
        )
        st.session_state["selected_node_id"] = selected

    for index, node in enumerate(workflow.get("nodes", [])):
        icon, status_label = STATUS.get(node.get("status"), ("·", node.get("status", "未知")))
        duration_ms = node.get("duration_ms")
        timing = f"{duration_ms:.0f}ms" if isinstance(duration_ms, (int, float)) else "—"
        prefix = "›" if node["id"] == selected else icon
        label = f'{prefix}  {node["order"]:02d}  {node["title"]}  ·  {status_label}  ·  {timing}'
        if st.button(label, key=f'node::{node["id"]}', help=node.get("description")):
            _set_selected_node(node["id"])
            st.rerun()
        if index < len(workflow["nodes"]) - 1:
            st.markdown('<div class="flow-arrow">↓</div>', unsafe_allow_html=True)


def _render_json_or_text(value):
    if isinstance(value, (dict, list)):
        st.json(value, expanded=1)
    elif value is None:
        st.caption("本节点没有记录该项内容。")
    else:
        st.code(str(value), language=None, wrap_lines=True)


def _render_source(relative_path):
    try:
        content = read_project_file(relative_path)
    except Exception as exc:
        st.error(str(exc))
        return
    suffix = Path(relative_path).suffix.lower()
    language = {
        ".py": "python",
        ".json": "json",
        ".md": "markdown",
        ".csv": "text",
        ".jsonl": "json",
    }.get(suffix, "text")
    st.markdown(f'<div class="source-path">{relative_path}</div>', unsafe_allow_html=True)
    if len(content) > 40000:
        st.caption("文件较大，工作台仅显示前40,000个字符；原文件未被修改。")
        content = content[:40000]
    st.code(content, language=language, line_numbers=True, wrap_lines=False)


def render_inspector(result):
    st.markdown('<div class="panel-label">对话与节点详情</div>', unsafe_allow_html=True)
    if not result:
        st.caption("尚无运行结果。你可以从“REM是什么？”或“我昨晚睡了多久？”开始。")
        return

    st.markdown(f'**用户**　{result.get("query", "")}')
    st.markdown(
        f'<div class="answer-box"><b>AI Coach</b><br>{result.get("answer", "")}</div>',
        unsafe_allow_html=True,
    )

    workflow = legacy_workflow_from_result(result)
    selected_id = st.session_state.get("selected_node_id")
    node = next((item for item in workflow.get("nodes", []) if item["id"] == selected_id), None)
    selected_source = st.session_state.get("selected_source_file")
    if selected_source:
        st.markdown(f'#### 文件：{Path(selected_source).name}')
        _render_source(selected_source)
        return
    if not node:
        st.caption("在中间点击一个节点查看详情。")
        return

    icon, status_label = STATUS.get(node.get("status"), ("·", node.get("status", "未知")))
    st.markdown(f'#### {icon} {node["title"]}')
    st.markdown(f'<div class="node-description">{node.get("description", "")}</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="status-line">{status_label} · {node.get("duration_ms", "—")}ms · '
        f'{node.get("category", "core")}</div>',
        unsafe_allow_html=True,
    )

    overview, input_tab, output_tab, source_tab = st.tabs(["概览", "输入", "输出", "源码"])
    with overview:
        meta = node.get("meta") or {}
        if meta:
            st.markdown("**运行元数据**")
            st.json(meta, expanded=2)
        else:
            st.caption("本节点没有额外运行元数据。")
        st.markdown("**传给下一步的内容**")
        _render_json_or_text(node.get("output"))
    with input_tab:
        _render_json_or_text(node.get("input"))
    with output_tab:
        _render_json_or_text(node.get("output"))
    with source_tab:
        files = expand_source_patterns(node.get("files") or [])
        if not files:
            st.caption("这个节点没有可展示的本地源码文件。")
        else:
            chosen = st.selectbox(
                "节点实现文件",
                files,
                key=f'source_select::{node["id"]}',
            )
            _render_source(chosen)


def render_studio(model, default_case, history):
    input_col, action_col = st.columns([4, 1])
    with input_col:
        st.markdown('<div class="studio-kicker">AI Coach observability</div>', unsafe_allow_html=True)
        st.markdown('<div class="studio-title">Workflow Studio</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="studio-subtitle">运行一次完整回答，逐节点查看输入、输出、Prompt、源码与传递过程。</div>',
            unsafe_allow_html=True,
        )
    with action_col:
        if model.configured:
            st.success("模型已连接")
        else:
            st.warning("模型未配置")

    left, center, right = st.columns([0.85, 1.2, 1.45], gap="medium")
    with right:
        with st.container(border=True):
            with st.form("workflow_query_form"):
                query = st.text_input(
                    "用户问题",
                    value=default_case["model_input"]["query"],
                    placeholder="输入一个睡眠或健康相关问题",
                )
                date_col, depth_col = st.columns([1, 1])
                with date_col:
                    date = st.text_input(
                        "Query Context Date",
                        value=default_case["model_input"]["query_context_date"],
                    )
                with depth_col:
                    response_depth = st.selectbox(
                        "回答深度",
                        ["brief", "insight", "coach"],
                        index=2,
                    )
                submitted = st.form_submit_button("运行完整链路", type="primary", use_container_width=True)
            if submitted:
                try:
                    with st.spinner("AI Coach正在运行完整工作流…"):
                        result = run_coach(
                            query,
                            date,
                            model,
                            response_depth=response_depth,
                            page_context="sleep_report",
                        )
                        record = append_run(result)
                    st.session_state["last"] = result
                    history.insert(0, record)
                    first_active = next(
                        node["id"] for node in result["trace"]["workflow"]["nodes"]
                        if node["status"] not in {"skipped", "pending"}
                    )
                    st.session_state["selected_node_id"] = first_active
                    st.session_state.pop("selected_source_file", None)
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

        render_inspector(st.session_state.get("last"))
    with left:
        with st.container(border=True):
            render_catalog()
    with center:
        with st.container(border=True):
            render_workflow(st.session_state.get("last"))


def history_download(history):
    return json.dumps(history, ensure_ascii=False, indent=2)


def render_evaluation_trace(eval_result):
    workflow = (eval_result or {}).get("workflow")
    if not workflow:
        return
    st.markdown("### Evaluation Workflow")
    graph_col, detail_col = st.columns([0.9, 1.4], gap="medium")
    selected_id = st.session_state.get("selected_eval_node_id")
    if not selected_id and workflow.get("nodes"):
        selected_id = workflow["nodes"][0]["id"]
        st.session_state["selected_eval_node_id"] = selected_id
    with graph_col:
        for index, node in enumerate(workflow.get("nodes", [])):
            icon, status_label = STATUS.get(node.get("status"), ("·", node.get("status", "未知")))
            timing = node.get("duration_ms")
            timing_text = f"{timing:.0f}ms" if isinstance(timing, (int, float)) else "—"
            prefix = "›" if node["id"] == selected_id else icon
            if st.button(
                f'{prefix}  {node["title"]} · {status_label} · {timing_text}',
                key=f'eval_node::{node["id"]}',
            ):
                st.session_state["selected_eval_node_id"] = node["id"]
                st.rerun()
            if index < len(workflow["nodes"]) - 1:
                st.markdown('<div class="flow-arrow">↓</div>', unsafe_allow_html=True)
    with detail_col:
        node = next((item for item in workflow.get("nodes", []) if item["id"] == selected_id), None)
        if not node:
            return
        st.markdown(f'#### {node["title"]}')
        st.caption(node.get("description", ""))
        input_tab, output_tab, source_tab = st.tabs(["输入", "输出", "源码"])
        with input_tab:
            _render_json_or_text(node.get("input"))
        with output_tab:
            _render_json_or_text(node.get("output"))
        with source_tab:
            files = expand_source_patterns(node.get("files") or [])
            if files:
                chosen = st.selectbox("实现文件", files, key=f'eval_source::{node["id"]}')
                _render_source(chosen)
            else:
                st.caption("没有可展示的本地文件。")
