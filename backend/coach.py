from .answer_planner import build_p02_answer_plan, load_answer_style_rules
from .insight_engine import build_p02_analysis
from .policy_engine import evaluate_routing, precheck_query
from .prompts import coach_messages
from .response_validator import validate_p02_response
from .retrieval import retrieve_for_route
from .router import route
from .workflow_trace import WorkflowTrace


INSIGHT_PROTOTYPES = {"P01", "P02", "P05", "P14"}


def _model_meta(model):
    return getattr(model, "last_call", None) or {}


def _result(query, query_context_date, response_depth, answer, trace, workflow):
    trace["workflow"] = workflow.as_dict()
    return {
        "query": query,
        "query_context_date": query_context_date,
        "response_depth": response_depth,
        "answer": answer,
        "trace": trace,
    }


def _skip_nodes(workflow, node_ids, reason):
    for node_id in node_ids:
        if workflow.node(node_id)["status"] == "pending":
            workflow.skip(node_id, reason)


def run_coach(
    query,
    query_context_date,
    model,
    response_depth="coach",
    page_context="sleep_report",
):
    trace = {}
    workflow = WorkflowTrace()

    input_payload = {
        "query": query,
        "query_context_date": query_context_date,
        "page_context": page_context,
        "response_depth": response_depth,
    }
    workflow.start("input_context", input_payload)
    workflow.finish("input_context", input_payload)

    workflow.start("safety_precheck", {"query": query})
    precheck = precheck_query(query)
    workflow.finish(
        "safety_precheck",
        {"matched": bool(precheck), "decision": precheck},
        status="blocked" if precheck else "success",
    )

    if precheck:
        synthetic_routing = {
            "module": "health",
            "task": precheck["task"],
            "prototype": "P25" if precheck["task"] == "emergency" else "none",
            "intent": "emergency_risk_triage" if precheck["task"] == "emergency" else precheck["task"],
            "answerability": "cannot_answer",
            "parameters": {},
        }
        trace["routing"] = {
            "parsed": synthetic_routing,
            "raw": None,
            "source": "deterministic_precheck",
        }
        trace["policy"] = precheck
        trace["retrieval"] = {"skipped": True, "reason": precheck["action"]}
        _skip_nodes(workflow, [
            "intent_router", "policy_gate", "retrieval_dispatch", "personal_data",
            "knowledge_base", "insight_engine", "answer_planner", "prompt_builder",
            "llm_generation", "response_validator",
        ], "确定性安全预检已拦截")
        workflow.start("final_response", {"decision": precheck})
        workflow.finish("final_response", {"answer": precheck["message"]})
        return _result(
            query, query_context_date, response_depth,
            precheck["message"], trace, workflow,
        )

    route_input = {
        "query": query,
        "context": {
            "query_context_date": query_context_date,
            "page_context": page_context,
            "response_depth": response_depth,
        },
    }
    workflow.start("intent_router", route_input)
    try:
        routing = route(query, route_input["context"], model)
    except Exception as exc:
        workflow.fail("intent_router", exc)
        raise
    trace["routing"] = routing
    workflow.finish(
        "intent_router",
        {"parsed": routing["parsed"], "raw": routing["raw"]},
        meta={"model_call": _model_meta(model)},
    )

    parsed = routing["parsed"]
    workflow.start("policy_gate", {"routing": parsed})
    policy = evaluate_routing(parsed)
    trace["policy"] = policy
    workflow.finish(
        "policy_gate",
        policy,
        status="success" if policy["action"] in {"allow", "allow_with_guardrails"} else "blocked",
    )
    if policy["action"] not in {"allow", "allow_with_guardrails"}:
        trace["retrieval"] = {"skipped": True, "reason": policy["action"]}
        _skip_nodes(workflow, [
            "retrieval_dispatch", "personal_data", "knowledge_base", "insight_engine",
            "answer_planner", "prompt_builder", "llm_generation", "response_validator",
        ], f'回答策略为{policy["action"]}')
        workflow.start("final_response", {"decision": policy})
        workflow.finish("final_response", {"answer": policy["message"]})
        return _result(
            query, query_context_date, response_depth,
            policy["message"], trace, workflow,
        )

    prototype = parsed["prototype"]
    target_node = "knowledge_base" if prototype == "P07" else "personal_data"
    workflow.start("retrieval_dispatch", {
        "prototype": prototype,
        "parameters": parsed.get("parameters") or {},
    })
    workflow.finish("retrieval_dispatch", {
        "target_node": target_node,
        "prototype": prototype,
    })
    if target_node == "knowledge_base":
        workflow.skip("personal_data", "P07使用术语知识库，不读取个人睡眠数据")
    else:
        workflow.skip("knowledge_base", f"{prototype}使用个人睡眠数据，不检索P07术语库")

    workflow.start(target_node, {
        "query_context_date": query_context_date,
        "prototype": prototype,
        "parameters": parsed.get("parameters") or {},
    })
    try:
        retrieved = retrieve_for_route(query_context_date, parsed, response_depth)
    except Exception as exc:
        workflow.fail(target_node, exc)
        raise
    trace["retrieval"] = retrieved
    workflow.finish(
        target_node,
        retrieved,
        status="success" if retrieved.get("available") else "error",
    )

    p02_analysis = None
    if prototype == "P02" and retrieved.get("available"):
        p02_analysis = build_p02_analysis(retrieved)
        retrieved["baseline_comparisons"] = p02_analysis["baseline_comparisons"]
        retrieved["insight_candidates"] = p02_analysis["insight_candidates"]

    if prototype in INSIGHT_PROTOTYPES and retrieved.get("available"):
        if prototype == "P01":
            insight_output = (retrieved.get("coach_payload") or {}).get("selected_insights", [])
        else:
            insight_output = retrieved.get("insight_candidates", [])
        workflow.start("insight_engine", {
            "prototype": prototype,
            "source": "retrieval_result",
            "metric_profile": retrieved.get("metric_profile"),
        })
        output = {"insight_candidates": insight_output}
        if p02_analysis:
            output.update({
                "baseline_comparisons": p02_analysis["baseline_comparisons"],
                "selection_policy": p02_analysis["selection_policy"],
            })
        workflow.finish("insight_engine", output)
    else:
        workflow.skip("insight_engine", f"{prototype}本次不需要洞察计算")

    if not retrieved.get("available"):
        answer = "我目前没有找到对应昨晚的有效睡眠数据，所以还不能可靠判断。"
        _skip_nodes(
            workflow,
            ["answer_planner", "prompt_builder", "llm_generation", "response_validator"],
            "检索结果不可用",
        )
        workflow.start("final_response", {"retrieval": retrieved})
        workflow.finish("final_response", {"answer": answer})
        return _result(query, query_context_date, response_depth, answer, trace, workflow)

    answer_plan = None
    if prototype == "P02":
        workflow.start("answer_planner", {
            "query": query,
            "metric_profile": retrieved.get("metric_profile"),
            "baseline_comparisons": retrieved.get("baseline_comparisons"),
            "insight_candidates": retrieved.get("insight_candidates"),
        })
        answer_plan = build_p02_answer_plan(
            query,
            retrieved,
            retrieved.get("insight_candidates") or [],
            response_depth=response_depth,
        )
        trace["answer_plan"] = answer_plan
        workflow.finish("answer_planner", answer_plan)
    else:
        workflow.skip("answer_planner", f"{prototype}尚未接入结构化Answer Plan")

    workflow.start("prompt_builder", {
        "query": query,
        "prototype": prototype,
        "retrieved": retrieved if prototype != "P02" else None,
        "answer_plan": answer_plan,
    })
    messages = coach_messages(query, retrieved, prototype, answer_plan=answer_plan)
    trace["generation_messages"] = messages
    workflow.finish("prompt_builder", {"messages": messages})

    workflow.start("llm_generation", {
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 1200,
    })
    try:
        answer = model.chat(messages, temperature=0.3, max_tokens=1200)
    except Exception as exc:
        workflow.fail("llm_generation", exc)
        raise
    workflow.finish(
        "llm_generation",
        {"raw_response": answer},
        meta={"model_call": _model_meta(model)},
    )

    if prototype == "P02":
        workflow.start("response_validator", {
            "answer": answer,
            "answer_plan": answer_plan,
        })
        initial_validation = validate_p02_response(answer, answer_plan)
        retry_record = None
        style = load_answer_style_rules()["P02"]
        if not initial_validation["valid"] and style.get("generation_retry_limit", 0) > 0:
            retry_messages = coach_messages(
                query,
                retrieved,
                prototype,
                answer_plan=answer_plan,
                validation_feedback=initial_validation["errors"],
            )
            retry_answer = model.chat(retry_messages, temperature=0.2, max_tokens=1200)
            retry_validation = validate_p02_response(retry_answer, answer_plan)
            retry_record = {
                "messages": retry_messages,
                "raw_response": retry_answer,
                "validation": retry_validation,
                "model_call": _model_meta(model),
            }
            answer = retry_answer
            final_validation = retry_validation
        else:
            final_validation = initial_validation
        trace["response_validation"] = {
            "initial": initial_validation,
            "retry": retry_record,
            "final": final_validation,
        }
        workflow.finish(
            "response_validator",
            trace["response_validation"],
            status="success" if final_validation["valid"] else "error",
        )
    else:
        workflow.skip("response_validator", f"{prototype}尚未接入P02事实校验器")

    trace["raw_generation"] = answer

    workflow.start("final_response", {"raw_generation": answer})
    workflow.finish("final_response", {"answer": answer})
    return _result(query, query_context_date, response_depth, answer, trace, workflow)
