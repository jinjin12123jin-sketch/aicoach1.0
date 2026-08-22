import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RULES_FILE = ROOT / "config" / "answerability_rules.json"

EMERGENCY_PATTERN = re.compile(
    r"胸痛|呼吸困难|喘不上气|昏厥|失去意识|自杀|不想活|大量出血"
)
MEDICATION_PATTERN = re.compile(
    r"开药|吃什么药|该吃.*药|停药|换药|加药|减药|调整剂量"
)
DIAGNOSIS_PATTERN = re.compile(
    r"我是不是.*病|是不是失眠|诊断|确诊|有没有.*疾病|得了什么病"
)


def load_answerability_rules():
    return json.loads(RULES_FILE.read_text(encoding="utf-8"))


def precheck_query(query):
    checks = [
        (EMERGENCY_PATTERN, "emergency"),
        (MEDICATION_PATTERN, "medication_request"),
        (DIAGNOSIS_PATTERN, "diagnosis_request"),
    ]
    for pattern, task in checks:
        if pattern.search(query):
            return decision_for_task(task, source="deterministic_precheck")
    return None


def decision_for_task(task, source="policy_matrix"):
    rules = load_answerability_rules()
    rule = rules["tasks"].get(task)
    if not rule:
        return {
            "task": task,
            "risk_level": "unknown",
            "action": rules["default_action"],
            "message": "当前回答规则库无法确认该问题是否可回答。",
            "source": source,
        }
    return {
        "task": task,
        "risk_level": rule["risk_level"],
        "action": rule["action"],
        "message": rule.get("message"),
        "allowed_prototypes": rule.get("allowed_prototypes", []),
        "source": source,
    }


def evaluate_routing(routing):
    prototype = routing.get("prototype")
    task = routing.get("task")
    if not task:
        task = {
            "P01": "personal_data_lookup",
            "P02": "personal_data_lookup",
            "P05": "personal_data_interpretation",
            "P07": "health_education",
            "P11": "personal_data_trend",
            "P12": "personal_data_trend",
            "P14": "personal_data_interpretation",
            "P25": "emergency",
        }.get(prototype, "out_of_scope")

    decision = decision_for_task(task)
    allowed = decision.get("allowed_prototypes") or []
    if decision["action"] in {"allow", "allow_with_guardrails"} and prototype not in allowed:
        return decision_for_task("out_of_scope", source="prototype_policy_mismatch")
    return decision
