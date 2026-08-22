import json
from pathlib import Path
import unittest
from unittest.mock import patch

from backend.answer_planner import build_p02_answer_plan
from backend.data_service import DEMO_DATA, resolve_sleep_data_path
from backend.coach import run_coach
from backend.evaluator import (
    load_case,
    load_cases,
    load_rubrics,
    retrieval_score,
    routing_score,
    run_eval,
)
from backend.knowledge_service import find_sleep_term, load_sleep_terms
from backend.insight_engine import build_p02_analysis
from backend.retrieval import retrieve_for_route
from backend.response_validator import validate_p02_response
from backend.workflow_trace import all_project_resources, sanitize


class SequenceModel:
    def __init__(self, responses):
        self.responses = iter(responses)

    def chat(self, messages, **kwargs):
        return next(self.responses)


def route_for(prototype, task, intent, parameters=None):
    return {
        "module": "sleep",
        "task": task,
        "prototype": prototype,
        "intent": intent,
        "answerability": "answer",
        "parameters": parameters or {},
    }


class MultiPrototypeTests(unittest.TestCase):
    def test_private_data_falls_back_to_repository_safe_demo(self):
        missing = Path("Z:/definitely-not-present/sleep_sessions.csv")
        with patch("backend.data_service.PRIVATE_DATA", missing):
            self.assertEqual(resolve_sleep_data_path(), DEMO_DATA)

    def test_case_ids_are_unique_and_cover_new_prototypes(self):
        cases = load_cases()
        ids = [case["case_id"] for case in cases]
        self.assertEqual(len(ids), len(set(ids)))
        for case_id in [
            "SLEEP_P02_001", "SLEEP_P05_001", "SLEEP_P07_001",
            "SLEEP_P11_001", "SLEEP_P12_001", "SLEEP_P14_001",
            "SAFETY_P25_001",
        ]:
            self.assertIn(case_id, ids)

    def test_p02_retrieves_duration_with_display_value(self):
        data = retrieve_for_route(
            "2026-05-07",
            route_for("P02", "personal_data_lookup", "time_duration_lookup", {"metric": "total_sleep_duration"}),
        )
        self.assertTrue(data["available"])
        self.assertEqual(data["display_value"], "7小时9分钟")
        score = retrieval_score(data, {
            "metric": "total_sleep_duration",
            "metric_family": "overall_duration",
            "default_companions": ["bedtime_start", "bedtime_end"],
        })
        self.assertEqual(score["score"], 1.0)

    def test_p02_boundary_uses_default_information_bundle(self):
        data = retrieve_for_route(
            "2026-05-07",
            route_for("P02", "personal_data_lookup", "time_duration_lookup", {"metric": "bedtime_start"}),
        )
        analysis = build_p02_analysis(data)
        data["baseline_comparisons"] = analysis["baseline_comparisons"]
        plan = build_p02_answer_plan(
            "我昨晚几点睡的？",
            data,
            analysis["insight_candidates"],
            response_depth="coach",
        )
        self.assertEqual(plan["query_focus"]["metric_family"], "sleep_boundary")
        companions = {item["id"] for item in plan["default_companions"]}
        self.assertEqual(companions, {"bedtime_end", "total_sleep_duration"})
        self.assertEqual(plan["required_facts"]["bedtime_start"]["display_value"], "23:31")

    def test_p02_rem_bundle_contains_duration_and_share(self):
        data = retrieve_for_route(
            "2026-05-07",
            route_for("P02", "personal_data_lookup", "time_duration_lookup", {"metric": "rem_sleep_duration"}),
        )
        analysis = build_p02_analysis(data)
        data["baseline_comparisons"] = analysis["baseline_comparisons"]
        plan = build_p02_answer_plan(
            "我昨晚REM睡了多久？",
            data,
            analysis["insight_candidates"],
            response_depth="coach",
        )
        self.assertEqual(plan["query_focus"]["metric_family"], "sleep_stage")
        self.assertEqual(plan["required_facts"]["rem_sleep_duration"]["display_value"], "1小时10分钟")
        self.assertEqual(plan["default_companions"][0]["id"], "rem_sleep_share")
        self.assertEqual(plan["default_companions"][0]["display_value"], "16%")

    def test_p02_builds_time_composition_candidate_from_supported_facts(self):
        data = retrieve_for_route(
            "2026-05-07",
            route_for("P02", "personal_data_lookup", "time_duration_lookup", {"metric": "bedtime_start"}),
        )
        baseline = data["baseline"]["metrics"]
        baseline["bedtime_start"].update({"center": 22 * 60 + 50, "mad": 0, "valid_sessions": 7})
        baseline["bedtime_end"].update({"center": 7 * 60 + 40, "mad": 0, "valid_sessions": 7})
        baseline["total_sleep_duration"].update({
            "center": data["current"]["total_sleep_duration"] + 40 * 60,
            "mad": 0,
            "valid_sessions": 7,
        })
        analysis = build_p02_analysis(data)
        ids = {item["id"] for item in analysis["insight_candidates"]}
        self.assertIn("schedule_change_explains_duration", ids)

    def test_p02_full_flow_exposes_answer_plan_and_validator(self):
        router_json = json.dumps(route_for(
            "P02", "personal_data_lookup", "time_duration_lookup", {"metric": "bedtime_start"}
        ), ensure_ascii=False)
        model = SequenceModel([
            router_json,
            "你昨晚大约23:31睡着，今天07:42醒来，一共睡了7小时9分钟。",
        ])
        result = run_coach("我昨晚几点睡的？", "2026-05-07", model, response_depth="coach")
        self.assertEqual(result["trace"]["answer_plan"]["prototype"], "P02")
        self.assertTrue(result["trace"]["response_validation"]["final"]["valid"])
        nodes = {node["id"]: node for node in result["trace"]["workflow"]["nodes"]}
        self.assertEqual(nodes["answer_planner"]["status"], "success")
        self.assertEqual(nodes["response_validator"]["status"], "success")

    def test_p02_invalid_first_answer_triggers_one_llm_rewrite(self):
        router_json = json.dumps(route_for(
            "P02", "personal_data_lookup", "time_duration_lookup", {"metric": "bedtime_start"}
        ), ensure_ascii=False)
        model = SequenceModel([
            router_json,
            "根据您的数据，您在2026年5月6日的入睡时间是23:31。原始数据未提供时区。",
            "你昨晚大约23:31睡着，今天07:42醒来，一共睡了7小时9分钟。",
        ])
        result = run_coach("我昨晚几点睡的？", "2026-05-07", model, response_depth="coach")
        validation = result["trace"]["response_validation"]
        self.assertFalse(validation["initial"]["valid"])
        self.assertIsNotNone(validation["retry"])
        self.assertTrue(validation["final"]["valid"])
        self.assertNotIn("根据您的数据", result["answer"])

    def test_p02_validator_rejects_report_preamble_and_internal_timezone(self):
        data = retrieve_for_route(
            "2026-05-07",
            route_for("P02", "personal_data_lookup", "time_duration_lookup", {"metric": "bedtime_start"}),
        )
        analysis = build_p02_analysis(data)
        data["baseline_comparisons"] = analysis["baseline_comparisons"]
        plan = build_p02_answer_plan("我昨晚几点睡的？", data, analysis["insight_candidates"])
        result = validate_p02_response(
            "根据您的数据，您在2026年5月6日23:31入睡。原始数据未提供时区。",
            plan,
        )
        self.assertFalse(result["valid"])
        self.assertGreaterEqual(len(result["errors"]), 3)

    def test_p02_validator_rejects_ungrounded_status_evaluation(self):
        data = retrieve_for_route(
            "2026-05-07",
            route_for("P02", "personal_data_lookup", "time_duration_lookup", {"metric": "total_sleep_duration"}),
        )
        analysis = build_p02_analysis(data)
        data["baseline_comparisons"] = analysis["baseline_comparisons"]
        plan = build_p02_answer_plan("我昨晚睡了多久？", data, analysis["insight_candidates"])
        result = validate_p02_response(
            "你昨晚睡了7小时9分钟，23:31睡着，07:42醒来，整体节奏比较规律。",
            plan,
        )
        self.assertFalse(result["valid"])
        self.assertTrue(any("状态评价" in error for error in result["errors"]))

    def test_p05_retrieves_night_and_baseline(self):
        data = retrieve_for_route(
            "2026-05-07",
            route_for("P05", "personal_data_interpretation", "multi_metric_night_summary"),
        )
        self.assertTrue(data["available"])
        self.assertEqual(len(data["night"]), 9)
        self.assertEqual(len(data["baseline_7d"]), 9)

    def test_p07_library_has_core_sleep_terms(self):
        library = load_sleep_terms()
        ids = {item["id"] for item in library["terms"]}
        self.assertTrue({"rem_sleep", "deep_sleep", "sleep_efficiency", "hrv"}.issubset(ids))
        result = find_sleep_term("hrv")
        self.assertTrue(result["available"])
        self.assertIn("相邻心跳间隔", result["term_entry"]["plain_definition"])
        self.assertEqual(result["review_status"], "product_draft_not_medically_approved")
        score = retrieval_score(result, {"term_id": "hrv"})
        self.assertEqual(score["score"], 1.0)

    def test_p07_coach_uses_knowledge_retrieval(self):
        router_json = json.dumps(route_for(
            "P07", "health_education", "sleep_metric_education", {"term": "rem_sleep"}
        ), ensure_ascii=False)
        model = SequenceModel([router_json, "REM是快速眼动睡眠；这是未医学审核的产品草案，不用于诊断。"])
        result = run_coach("REM是什么？", "2026-05-07", model, response_depth="brief")
        self.assertEqual(result["trace"]["routing"]["parsed"]["prototype"], "P07")
        self.assertEqual(result["trace"]["retrieval"]["term_entry"]["id"], "rem_sleep")
        nodes = {
            node["id"]: node
            for node in result["trace"]["workflow"]["nodes"]
        }
        self.assertEqual(nodes["knowledge_base"]["status"], "success")
        self.assertEqual(nodes["personal_data"]["status"], "skipped")
        self.assertEqual(nodes["llm_generation"]["status"], "success")
        self.assertEqual(nodes["history_persistence"]["status"], "pending")
        self.assertEqual(
            nodes["prompt_builder"]["output"]["messages"][0]["role"],
            "system",
        )

    def test_p11_compares_two_windows(self):
        data = retrieve_for_route(
            "2026-05-07",
            route_for("P11", "personal_data_trend", "period_trend_comparison", {
                "metric": "total_sleep_duration", "window_sessions": 7
            }),
        )
        self.assertTrue(data["available"])
        self.assertEqual(data["current_window"]["valid_sessions"], 7)
        self.assertEqual(data["previous_window"]["valid_sessions"], 7)

    def test_p12_uses_personal_baseline(self):
        data = retrieve_for_route(
            "2026-05-07",
            route_for("P12", "personal_data_trend", "personal_baseline_deviation", {"metric": "average_hrv"}),
        )
        self.assertTrue(data["available"])
        self.assertEqual(data["current"], 96.0)
        self.assertLess(data["delta"], 0)
        self.assertIn("尚未计算个人常见波动区间", data["limit"])

    def test_p14_reuses_grounded_insights(self):
        data = retrieve_for_route(
            "2026-05-07",
            route_for("P14", "personal_data_interpretation", "sleep_domain_analysis"),
        )
        self.assertTrue(data["available"])
        self.assertTrue(data["insight_candidates"])
        self.assertIn("不得诊断失眠", data["analysis_limit"])

    def test_out_of_scope_skips_retrieval(self):
        router_json = json.dumps({
            "module": "unsupported", "task": "out_of_scope", "prototype": "none",
            "intent": "out_of_scope", "answerability": "cannot_answer", "parameters": {},
        })
        result = run_coach("蜘蛛侠好看吗？", "2026-05-07", SequenceModel([router_json]))
        self.assertTrue(result["trace"]["retrieval"]["skipped"])

    def test_case_driven_routing_score(self):
        case = load_case("SLEEP_P07_001")
        route = {**case["expected_routing"], "parameters": dict(case["expected_parameters"])}
        self.assertEqual(
            routing_score(route, case["expected_routing"], case["expected_parameters"])["score"],
            1.0,
        )
        self.assertEqual(len(load_rubrics(case)), 6)

    def test_emergency_precheck_maps_to_p25_and_bypasses_model(self):
        class MustNotRunModel:
            def chat(self, messages, **kwargs):
                raise AssertionError("紧急风险预检后不应再调用模型")

        result = run_coach("我胸痛而且呼吸困难怎么办？", "2026-05-07", MustNotRunModel())
        parsed = result["trace"]["routing"]["parsed"]
        self.assertEqual(parsed["task"], "emergency")
        self.assertEqual(parsed["prototype"], "P25")
        self.assertTrue(result["trace"]["retrieval"]["skipped"])
        self.assertIn("120", result["answer"])
        nodes = {
            node["id"]: node
            for node in result["trace"]["workflow"]["nodes"]
        }
        self.assertEqual(nodes["safety_precheck"]["status"], "blocked")
        self.assertEqual(nodes["intent_router"]["status"], "skipped")
        self.assertEqual(nodes["final_response"]["status"], "success")

    def test_workflow_catalog_covers_all_python_and_json_files(self):
        groups = all_project_resources()
        files = {
            path
            for group in groups
            for path in group["resolved_files"]
        }
        self.assertIn("backend/coach.py", files)
        self.assertIn("config/knowledge/sleep_terms.json", files)
        self.assertIn("tests/test_core.py", files)
        self.assertIn("config/workflow_modules.json", files)

    def test_workflow_trace_redacts_sensitive_keys(self):
        data = sanitize({"api_key": "secret", "nested": {"token": "secret"}})
        self.assertEqual(data["api_key"], "[REDACTED]")
        self.assertEqual(data["nested"]["token"], "[REDACTED]")

    def test_evaluation_has_clickable_node_trace_data(self):
        case = load_case("SLEEP_P07_001")
        route = {**case["expected_routing"], "parameters": dict(case["expected_parameters"])}
        retrieval = find_sleep_term("rem_sleep")
        judge_response = json.dumps({"criteria_met": True, "explanation": "test"})
        result = run_eval(
            case,
            "REM是快速眼动睡眠；这是产品草案，不用于诊断。",
            route,
            SequenceModel([judge_response] * len(load_rubrics(case))),
            retrieval,
        )
        nodes = {node["id"]: node for node in result["workflow"]["nodes"]}
        self.assertEqual(nodes["eval_case"]["status"], "success")
        self.assertEqual(nodes["eval_judge"]["status"], "success")
        self.assertEqual(nodes["eval_summary"]["status"], "success")


if __name__ == "__main__":
    unittest.main()
