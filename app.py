import json

import streamlit as st

from backend.env import load_dotenv_if_present
from backend.evaluator import load_case, load_cases, run_eval
from backend.history_service import load_runs
from backend.model_adapter import OpenAICompatibleModel
from backend.workflow_trace import legacy_workflow_from_result
from ui.workflow_studio import (
    history_download,
    inject_workflow_css,
    render_evaluation_trace,
    render_studio,
)


load_dotenv_if_present()
st.set_page_config(
    page_title="AI Coach Workflow Studio",
    page_icon="◫",
    layout="wide",
    initial_sidebar_state="collapsed",
)
inject_workflow_css()

default_case = load_case()
cases = load_cases()
cases_by_id = {item["case_id"]: item for item in cases}
model = OpenAICompatibleModel()

if "history" not in st.session_state:
    st.session_state["history"] = load_runs()
if "last" not in st.session_state and st.session_state["history"]:
    st.session_state["last"] = st.session_state["history"][0]["result"]
if "workspace_page" not in st.session_state:
    st.session_state["workspace_page"] = "Workflow Studio"


def routing_for_result(result):
    return ((((result or {}).get("trace") or {}).get("routing") or {}).get("parsed") or {})


def case_compatible(result, item):
    if not result:
        return False
    actual = routing_for_result(result)
    expected = item["expected_routing"]
    expected_parameters = item.get("expected_parameters", {})
    actual_parameters = actual.get("parameters") or {}
    return (
        result.get("query_context_date") == item["model_input"]["query_context_date"]
        and result.get("response_depth", "coach") == item["model_input"].get("response_depth", "coach")
        and all(actual.get(key) == value for key, value in expected.items())
        and all(actual_parameters.get(key) == value for key, value in expected_parameters.items())
    )


nav_col, info_col = st.columns([3, 1])
with nav_col:
    page = st.segmented_control(
        "工作区",
        ["Workflow Studio", "Evaluation", "Run History"],
        key="workspace_page",
        label_visibility="collapsed",
    )
with info_col:
    st.caption("Read-only workflow · Local trace · No secret exposure")


if page == "Workflow Studio":
    render_studio(model, default_case, st.session_state["history"])

elif page == "Evaluation":
    st.markdown('<div class="studio-kicker">AI Coach evaluation</div>', unsafe_allow_html=True)
    st.markdown('<div class="studio-title">Evaluation</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="studio-subtitle">只对语义、日期、原型和参数兼容的Bench Case运行评分。</div>',
        unsafe_allow_html=True,
    )
    current = st.session_state.get("last")
    if not current:
        st.info("请先在Workflow Studio运行一次回答。")
    else:
        actual = routing_for_result(current)
        matching = [item for item in cases if case_compatible(current, item)]
        exact = next(
            (
                item for item in matching
                if current.get("query", "").strip() == item["model_input"]["query"].strip()
            ),
            None,
        )
        suggested = exact or (matching[0] if matching else default_case)
        case_ids = [item["case_id"] for item in cases]
        selected_case_id = st.selectbox(
            "选择Bench Case",
            case_ids,
            index=case_ids.index(suggested["case_id"]),
            format_func=lambda case_id: (
                f'{case_id} · {cases_by_id[case_id].get("name", cases_by_id[case_id]["model_input"]["query"])}'
            ),
        )
        eval_case = cases_by_id[selected_case_id]
        compatible = case_compatible(current, eval_case)

        run_col, case_col = st.columns([1, 1], gap="large")
        with run_col:
            st.markdown("#### 当前Candidate")
            st.write(current.get("query", ""))
            st.caption(
                f'{actual.get("prototype", "—")} · {actual.get("intent", "—")} · '
                f'{current.get("query_context_date", "—")}'
            )
            st.markdown(current.get("answer", ""))
        with case_col:
            st.markdown("#### Bench Case")
            st.write(eval_case["model_input"]["query"])
            st.caption(
                f'{eval_case["expected_routing"].get("prototype", "—")} · '
                f'{eval_case["expected_routing"].get("intent", "—")} · '
                f'{eval_case["model_input"]["query_context_date"]}'
            )
            if compatible:
                st.success("当前运行与Case语义兼容，可以评分。")
            else:
                st.warning("日期、回答深度、路由或参数不兼容，已禁止套用该Case评分。")

        with st.expander("查看Bench Case原始配置"):
            st.json(eval_case)

        if st.button("运行Evaluation Workflow", type="primary", disabled=not compatible):
            try:
                with st.spinner("Judge正在逐条执行Rubric…"):
                    eval_result = run_eval(
                        eval_case,
                        current["answer"],
                        actual,
                        model,
                        (current.get("trace") or {}).get("retrieval"),
                    )
                st.session_state["last_eval"] = eval_result
                st.session_state["selected_eval_node_id"] = "eval_case"
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

        eval_result = st.session_state.get("last_eval")
        if eval_result:
            score_a, score_b, score_c = st.columns(3)
            score_a.metric("Routing Score", f'{eval_result["routing_score"]["score"] * 100:.0f}%')
            retrieval = eval_result.get("retrieval_score")
            score_b.metric(
                "Retrieval Score",
                f'{retrieval["score"] * 100:.0f}%' if retrieval else "N/A",
            )
            score_c.metric("Response Score", f'{eval_result["response_score"] * 100:.1f}%')
            render_evaluation_trace(eval_result)
            st.markdown("### Rubric结果")
            for item in eval_result["rubric_results"]:
                rubric = item["rubric"]
                icon = "✓" if item["criteria_met"] else "×"
                st.markdown(f'**{icon} {rubric["id"]} · {rubric["points"]:+}** — {rubric["criterion"]}')
                st.caption(item["explanation"])
            with st.expander("Ground Truth / Evaluator Only"):
                st.json(eval_result["ground_truth"])
            st.info(eval_result["limitation"])

else:
    st.markdown('<div class="studio-kicker">Local research archive</div>', unsafe_allow_html=True)
    st.markdown('<div class="studio-title">Run History</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="studio-subtitle">重新打开过去的对话和节点Trace，用于复盘Case与比较执行路径。</div>',
        unsafe_allow_html=True,
    )
    history = st.session_state["history"]
    if not history:
        st.info("还没有运行记录。")
    else:
        st.download_button(
            "下载全部记录（JSON）",
            data=history_download(history),
            file_name="ai_coach_history.json",
            mime="application/json",
        )
        for record in history:
            result = record["result"]
            routing = routing_for_result(result)
            workflow = legacy_workflow_from_result(result)
            label = (
                f'{record["created_at"]} · {routing.get("prototype", "—")} · '
                f'{result.get("query", "未知问题")}'
            )
            with st.expander(label):
                summary_col, action_col = st.columns([4, 1])
                with summary_col:
                    st.write(result.get("answer", ""))
                    st.caption(
                        f'{len(workflow.get("nodes", []))} nodes · '
                        f'{workflow.get("duration_ms", "—")}ms · Run ID {record.get("run_id", "—")}'
                    )
                with action_col:
                    if st.button("在Studio打开", key=f'open::{record.get("run_id")}', use_container_width=True):
                        st.session_state["last"] = result
                        st.session_state["workspace_page"] = "Workflow Studio"
                        st.session_state["selected_node_id"] = "input_context"
                        st.session_state.pop("selected_source_file", None)
                        st.rerun()
                with st.expander("完整节点Trace"):
                    st.json(workflow)
