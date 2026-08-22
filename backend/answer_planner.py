import copy
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
METRIC_PROFILES_FILE = ROOT / "config" / "metric_profiles.json"
RELATIONSHIPS_FILE = ROOT / "config" / "metric_relationships.json"
STYLE_RULES_FILE = ROOT / "config" / "answer_style_rules.json"


def _load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_metric_profiles():
    return _load_json(METRIC_PROFILES_FILE)


def load_metric_relationships():
    return _load_json(RELATIONSHIPS_FILE)


def load_answer_style_rules():
    return _load_json(STYLE_RULES_FILE)


def get_p02_metric_profile(metric):
    config = load_metric_profiles()
    metric_config = copy.deepcopy((config.get("metrics") or {}).get(metric))
    if not metric_config:
        raise KeyError(f"P02没有配置指标画像：{metric}")
    family_id = metric_config["family"]
    metric_config["metric"] = metric
    metric_config["family_id"] = family_id
    metric_config["family"] = copy.deepcopy(config["families"][family_id])
    metric_config["baseline_sessions"] = config.get("baseline_sessions", 7)
    metric_config["minimum_baseline_sessions"] = config.get("minimum_baseline_sessions", 4)
    return metric_config


def _relative_time_phrase(query):
    for phrase in ("昨晚", "昨天晚上", "昨天夜里", "今早", "今天早上", "前天"):
        if phrase in query:
            return phrase
    return None


def build_p02_answer_plan(query, retrieved, candidate_insights, response_depth="coach"):
    metric = retrieved["metric"]
    profile = retrieved["metric_profile"]
    style = copy.deepcopy(load_answer_style_rules()["P02"])
    max_insights = (style.get("max_optional_insights_by_depth") or {}).get(response_depth, 1)

    requested_fact = copy.deepcopy(retrieved["current_facts"][metric])
    requested_fact["measurement_qualifier"] = profile.get("measurement_qualifier")

    companions = []
    for companion_id in profile.get("default_companions", []):
        if companion_id == "target_baseline_comparison":
            comparison = (retrieved.get("baseline_comparisons") or {}).get(metric)
            if comparison and comparison.get("baseline_available"):
                companions.append({
                    "id": companion_id,
                    "type": "personal_baseline_comparison",
                    **copy.deepcopy(comparison),
                })
            continue
        fact = (retrieved.get("current_facts") or {}).get(companion_id)
        fact = fact or (retrieved.get("computed_facts") or {}).get(companion_id)
        if fact and fact.get("available", True):
            companions.append({"id": companion_id, "type": "fact", **copy.deepcopy(fact)})

    safe_candidates = copy.deepcopy(candidate_insights[:3]) if max_insights else []
    return {
        "schema_version": "0.1",
        "prototype": "P02",
        "user_query": query,
        "query_focus": {
            "metric": metric,
            "metric_label": retrieved["metric_label"],
            "relative_time_phrase": _relative_time_phrase(query),
            "metric_family": profile["family_id"],
            "metric_family_name": profile["family"]["name"],
        },
        "required_facts": {
            metric: requested_fact,
        },
        "default_companions": companions,
        "candidate_insights": safe_candidates,
        "answer_policy": {
            "response_depth": response_depth,
            "answer_query_first": style["answer_query_first"],
            "include_default_companions": style["include_default_companions"],
            "max_optional_insights": max_insights,
            "allow_no_insight": style["allow_no_insight"],
            "address_user_as": style["address_user_as"],
            "tone": style["tone"],
            "avoid_preambles": style["avoid_preambles"],
            "hide_unless_asked": style["hide_unless_asked"],
            "forbidden_claim_fragments": style["forbidden_claim_fragments"],
            "ungrounded_evaluation_fragments": style["ungrounded_evaluation_fragments"],
        },
    }
