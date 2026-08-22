
import json, re
from pathlib import Path
from .data_service import get_night_and_baseline
from .prompts import judge_messages
from .workflow_trace import WorkflowTrace

ROOT = Path(__file__).resolve().parents[1]

def load_cases():
    cases = []
    for path in sorted((ROOT / "bench").rglob("*.json")):
        case = json.loads(path.read_text(encoding="utf-8"))
        case["_source_file"] = str(path.relative_to(ROOT)).replace("\\", "/")
        cases.append(case)
    return cases


def load_case(case_id="SLEEP_P05_001"):
    cases = load_cases()
    case = next((item for item in cases if item["case_id"] == case_id), None)
    if not case:
        raise KeyError(f"找不到 Bench Case：{case_id}")
    return case


def load_rubrics(case):
    files = case.get("rubric_files")
    if not files and case.get("rubric_file"):
        files = [case["rubric_file"]]
    if not files:
        raise ValueError(f'{case["case_id"]} 没有配置 rubric_files')

    rubrics = []
    for relative_path in files:
        path = (ROOT / relative_path).resolve()
        if ROOT.resolve() not in path.parents:
            raise ValueError(f"Rubric 路径越出项目目录：{relative_path}")
        rubrics.extend(json.loads(path.read_text(encoding="utf-8")))
    return rubrics

def routing_score(pred, expected, expected_parameters=None):
    fields = ["module", "prototype", "intent", "answerability"]
    if "task" in expected:
        fields.insert(1, "task")
    details = {f:{"expected":expected.get(f),"actual":pred.get(f),"ok":pred.get(f)==expected.get(f)} for f in fields}
    for name, value in (expected_parameters or {}).items():
        key = f"parameters.{name}"
        actual = (pred.get("parameters") or {}).get(name)
        details[key] = {"expected": value, "actual": actual, "ok": actual == value}
    return {"score":sum(v["ok"] for v in details.values())/len(details),"details":details}


def retrieval_score(pred, expected):
    if not expected:
        return None
    pred = pred or {}
    details = {}
    details["available"] = {
        "expected": True,
        "actual": bool(pred.get("available")),
        "ok": bool(pred.get("available")),
    }
    actual_fields = set((pred.get("night") or {}).keys())
    for field in expected.get("night_fields", []):
        details[f"night.{field}"] = {
            "expected": "present",
            "actual": "present" if field in actual_fields else "missing",
            "ok": field in actual_fields,
        }
    expected_metric = expected.get("metric")
    if expected_metric:
        actual_metric = pred.get("metric")
        details["metric"] = {
            "expected": expected_metric,
            "actual": actual_metric,
            "ok": actual_metric == expected_metric,
        }
        details["value"] = {
            "expected": "present",
            "actual": "present" if pred.get("value") is not None else "missing",
            "ok": pred.get("value") is not None,
        }
    expected_term_id = expected.get("term_id")
    if expected_term_id:
        actual_term_id = (pred.get("term_entry") or {}).get("id")
        details["term_entry.id"] = {
            "expected": expected_term_id,
            "actual": actual_term_id,
            "ok": actual_term_id == expected_term_id,
        }
    expected_baseline = expected.get("baseline")
    if expected_baseline:
        has_baseline = bool(pred.get("baseline_7d"))
        details["baseline"] = {
            "expected": expected_baseline,
            "actual": "baseline_7d" if has_baseline else "missing",
            "ok": has_baseline,
        }
    expected_family = expected.get("metric_family")
    if expected_family:
        actual_family = (pred.get("metric_profile") or {}).get("family_id")
        details["metric_profile.family_id"] = {
            "expected": expected_family,
            "actual": actual_family,
            "ok": actual_family == expected_family,
        }
    expected_companions = expected.get("default_companions") or []
    actual_companions = set((pred.get("metric_profile") or {}).get("default_companions") or [])
    for companion in expected_companions:
        present = companion in actual_companions
        details[f"default_companions.{companion}"] = {
            "expected": "configured",
            "actual": "configured" if present else "missing",
            "ok": present,
        }
    return {
        "score": sum(v["ok"] for v in details.values()) / len(details),
        "details": details,
    }

def run_eval(case, candidate_answer, routing_pred, model, retrieval_pred=None):
    workflow = WorkflowTrace(flow="evaluation")
    workflow.start("eval_case", {"case_id": case["case_id"]})
    workflow.finish("eval_case", {
        "case_id": case["case_id"],
        "name": case.get("name"),
        "model_input": case.get("model_input"),
        "expected_routing": case.get("expected_routing"),
        "expected_parameters": case.get("expected_parameters"),
        "rubric_files": case.get("rubric_files"),
    })

    workflow.start("eval_compatibility", {
        "actual_routing": routing_pred,
        "expected_routing": case["expected_routing"],
    })
    expected = case["expected_routing"]
    expected_parameters = case.get("expected_parameters") or {}
    actual_parameters = routing_pred.get("parameters") or {}
    compatible = (
        all(routing_pred.get(key) == value for key, value in expected.items())
        and all(actual_parameters.get(key) == value for key, value in expected_parameters.items())
    )
    workflow.finish(
        "eval_compatibility",
        {"compatible": compatible},
        status="success" if compatible else "blocked",
    )

    gt = get_night_and_baseline(case["model_input"]["query_context_date"])
    workflow.start("eval_routing", {
        "routing_pred": routing_pred,
        "retrieval_pred": retrieval_pred,
    })
    rscore = routing_score(
        routing_pred,
        case["expected_routing"],
        case.get("expected_parameters"),
    )
    retrieval_result = retrieval_score(retrieval_pred, case.get("expected_retrieval"))
    workflow.finish("eval_routing", {
        "routing_score": rscore,
        "retrieval_score": retrieval_result,
    })

    results = []
    rubrics = load_rubrics(case)
    workflow.start("eval_judge", {
        "candidate_answer": candidate_answer,
        "rubrics": rubrics,
    })
    try:
        for rubric in rubrics:
            raw = model.chat(
                judge_messages(case["model_input"]["query"], gt, candidate_answer, rubric),
                temperature=0.0,
                max_tokens=700,
                json_mode=True,
                retries=2,
                thinking=False,
            )
            cleaned = re.sub(r"^```json\s*|\s*```$", "", raw.strip())
            try:
                parsed = json.loads(cleaned)
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    f'Judge 在 Rubric {rubric.get("id", "unknown")} 返回了无效 JSON：{exc.msg}'
                ) from exc
            results.append({
                "rubric":rubric,
                "criteria_met":bool(parsed.get("criteria_met")),
                "explanation":parsed.get("explanation","")
            })
    except Exception as exc:
        workflow.fail("eval_judge", exc)
        raise
    workflow.finish("eval_judge", {"rubric_results": results}, meta={
        "rubric_count": len(rubrics),
        "last_model_call": getattr(model, "last_call", None),
    })

    pos = sum(x["rubric"]["points"] for x in results if x["rubric"]["points"] > 0)
    achieved = sum(x["rubric"]["points"] for x in results if x["criteria_met"])
    summary = {
        "routing_score":rscore,
        "retrieval_score":retrieval_result,
        "response_score": achieved/pos if pos else None,
        "rubric_results":results,
        "ground_truth":gt,
        "limitation":"v0.1 可让同一模型兼任 Candidate 与 Judge；存在 Judge Bias，后续应引入独立 Judge 或人工抽检。"
    }
    workflow.start("eval_summary", {"rubric_results": results})
    workflow.finish("eval_summary", {
        "routing_score": rscore["score"],
        "retrieval_score": retrieval_result["score"] if retrieval_result else None,
        "response_score": summary["response_score"],
    })
    summary["workflow"] = workflow.as_dict()
    return summary
