import json
from pathlib import Path

from .answer_planner import get_p02_metric_profile, load_metric_relationships


ROOT = Path(__file__).resolve().parents[1]
CLAIMS_FILE = ROOT / "config" / "health_claims.json"


def load_health_claims():
    return json.loads(CLAIMS_FILE.read_text(encoding="utf-8"))


def format_duration(seconds):
    total_minutes = round(float(seconds) / 60)
    hours, minutes = divmod(total_minutes, 60)
    if hours and minutes:
        return f"{hours}小时{minutes}分钟"
    if hours:
        return f"{hours}小时"
    return f"{minutes}分钟"


def display_metric(metric, value, unit):
    if unit == "seconds":
        return format_duration(value)
    if unit == "percent":
        return f"{float(value):.1f}".rstrip("0").rstrip(".") + "%"
    if unit == "bpm":
        return f"{value:g}次/分"
    if unit == "ms":
        return f"{value:g}ms"
    if unit == "breaths_per_minute":
        return f"{value:g}次/分"
    return f"{value:g}"


def display_p02_value(metric, value, unit):
    if value is None:
        return None
    if unit == "datetime":
        text = str(value)
        if "T" in text:
            return text.split("T", 1)[1][:5]
        return text[-5:]
    return display_metric(metric, value, unit)


def display_clock_minutes(value):
    total = round(float(value)) % 1440
    hours, minutes = divmod(total, 60)
    return f"{hours:02d}:{minutes:02d}"


def _comparison_measure(metric, current, baseline_entry):
    unit = baseline_entry["unit"]
    center = baseline_entry["center"]
    mad = baseline_entry.get("mad") or 0.0
    if unit == "clock_minutes":
        current_minutes = int(str(current)[11:13]) * 60 + int(str(current)[14:16])
        delta = ((current_minutes - center + 720) % 1440) - 720
        return delta, mad, "minutes"
    if unit == "seconds":
        return (float(current) - float(center)) / 60, float(mad) / 60, "minutes"
    if unit == "percent":
        return float(current) - float(center), float(mad), "percentage_points"
    return float(current) - float(center), float(mad), unit


def _comparison_direction(metric, delta):
    if metric in {"bedtime_start", "bedtime_end"}:
        return "later" if delta > 0 else "earlier" if delta < 0 else "stable"
    if metric in {"total_sleep_duration", "time_in_bed", "deep_sleep_duration", "rem_sleep_duration"}:
        return "longer" if delta > 0 else "shorter" if delta < 0 else "stable"
    if metric in {"awake_time", "latency"}:
        return "more" if delta > 0 else "less" if delta < 0 else "stable"
    return "higher" if delta > 0 else "lower" if delta < 0 else "stable"


def _comparison_fact(metric, label, delta, unit):
    magnitude = round(abs(delta)) if unit == "minutes" else round(abs(delta), 1)
    if unit == "minutes":
        suffix = f"{magnitude}分钟"
    elif unit == "percentage_points":
        suffix = f"{magnitude:g}个百分点"
    else:
        suffix = f"{magnitude:g}{unit}"
    direction = _comparison_direction(metric, delta)
    words = {
        "later": "晚",
        "earlier": "早",
        "longer": "长",
        "shorter": "短",
        "more": "多",
        "less": "少",
        "higher": "高",
        "lower": "低",
        "stable": "接近",
    }
    if direction == "stable":
        return f"{label}与个人近期水平接近"
    return f"{label}比个人近期水平{words[direction]}{suffix}"


def _metric_threshold(metric):
    if metric == "efficiency":
        return 4.0, 4
    profile = get_p02_metric_profile(metric)
    return float(profile["minimum_noticeable_change"]), int(profile["minimum_baseline_sessions"])


def build_p02_analysis(retrieved):
    """Build auditable comparisons and safe candidate insights for P02.

    The result contains structured facts and allowed claim scopes. It does not
    generate the final user-facing answer.
    """
    current = retrieved.get("current") or {}
    baseline_metrics = ((retrieved.get("baseline") or {}).get("metrics") or {})
    current_facts = retrieved.get("current_facts") or {}
    relationships = load_metric_relationships()["relationships"]
    comparisons = {}

    for metric, value in current.items():
        baseline_entry = baseline_metrics.get(metric)
        fact = current_facts.get(metric)
        if value is None or not baseline_entry or not fact:
            continue
        delta, mad, unit = _comparison_measure(metric, value, baseline_entry)
        minimum_change, minimum_sessions = _metric_threshold(metric)
        personal_noise_floor = 2 * mad
        effective_threshold = max(minimum_change, personal_noise_floor)
        valid_sessions = int(baseline_entry.get("valid_sessions") or 0)
        baseline_available = valid_sessions >= minimum_sessions
        noticeable = baseline_available and abs(delta) >= effective_threshold
        comparisons[metric] = {
            "metric": metric,
            "metric_label": fact["label"],
            "baseline_available": baseline_available,
            "valid_sessions": valid_sessions,
            "baseline_window": (retrieved.get("baseline") or {}).get("window"),
            "current_display": fact["display_value"],
            "baseline_display": (
                display_clock_minutes(baseline_entry["center"])
                if baseline_entry["unit"] == "clock_minutes"
                else display_p02_value(metric, baseline_entry["center"], baseline_entry["unit"])
            ),
            "delta": round(delta, 1),
            "delta_unit": unit,
            "direction": _comparison_direction(metric, delta),
            "minimum_noticeable_change": minimum_change,
            "personal_noise_floor": round(personal_noise_floor, 1),
            "effective_threshold": round(effective_threshold, 1),
            "noticeable": noticeable,
            "fact": _comparison_fact(metric, fact["label"], delta, unit),
        }

    target_metric = retrieved["metric"]
    profile = retrieved["metric_profile"]
    candidates = []
    target_comparison = comparisons.get(target_metric)
    if target_comparison and target_comparison["noticeable"]:
        family_relation = {
            "sleep_boundary": "schedule_vs_baseline",
            "overall_duration": "duration_vs_baseline",
            "sleep_stage": "stage_vs_baseline",
            "continuity_duration": "continuity_vs_baseline",
        }[profile["family_id"]]
        relationship = relationships[family_relation]
        candidates.append({
            "id": f"{target_metric}_vs_personal_baseline",
            "relation_id": family_relation,
            "relation_type": relationship["relation_type"],
            "priority": 0.82,
            "relevance_to_query": "high",
            "evidence_strength": relationship["evidence_strength"],
            "facts": [target_comparison["fact"]],
            "allowed_claim": relationship["allowed_scope"],
            "forbidden_claims": relationship["forbidden_scope"],
        })

    start = comparisons.get("bedtime_start")
    end = comparisons.get("bedtime_end")
    duration = comparisons.get("total_sleep_duration")
    if start and end and duration:
        start_changed = start["noticeable"]
        end_changed = end["noticeable"]
        duration_changed = duration["noticeable"]
        relation = None
        allowed_claim = None
        if start_changed and not end_changed and duration_changed:
            if start["direction"] == "later" and duration["direction"] == "shorter":
                allowed_claim = "这晚减少的睡眠主要出现在更晚入睡这一段"
            elif start["direction"] == "earlier" and duration["direction"] == "longer":
                allowed_claim = "这晚增加的睡眠主要来自更早入睡留出的时间"
            relation = "schedule_explains_duration" if allowed_claim else None
        elif end_changed and not start_changed and duration_changed:
            if end["direction"] == "earlier" and duration["direction"] == "shorter":
                allowed_claim = "这晚减少的睡眠主要出现在更早醒来的这一段"
            elif end["direction"] == "later" and duration["direction"] == "longer":
                allowed_claim = "这晚增加的睡眠主要来自更晚醒来留出的时间"
            relation = "schedule_explains_duration" if allowed_claim else None
        if relation and relation in profile.get("candidate_relationships", []):
            relationship = relationships[relation]
            candidates.append({
                "id": "schedule_change_explains_duration",
                "relation_id": relation,
                "relation_type": relationship["relation_type"],
                "priority": 0.98,
                "relevance_to_query": "high",
                "evidence_strength": relationship["evidence_strength"],
                "facts": [start["fact"], end["fact"], duration["fact"]],
                "allowed_claim": allowed_claim,
                "forbidden_claims": relationship["forbidden_scope"],
            })

    awake = comparisons.get("awake_time")
    efficiency = comparisons.get("efficiency")
    if (
        target_metric in {"total_sleep_duration", "awake_time"}
        and awake and efficiency and awake["noticeable"] and efficiency["noticeable"]
        and "awake_and_efficiency_move_together" in profile.get("candidate_relationships", [])
    ):
        relationship = relationships["awake_and_efficiency_move_together"]
        candidates.append({
            "id": "awake_and_efficiency_move_together",
            "relation_id": "awake_and_efficiency_move_together",
            "relation_type": relationship["relation_type"],
            "priority": 0.9,
            "relevance_to_query": "high",
            "evidence_strength": relationship["evidence_strength"],
            "facts": [awake["fact"], efficiency["fact"]],
            "allowed_claim": relationship["allowed_scope"],
            "forbidden_claims": relationship["forbidden_scope"],
        })

    # Keep only relationships explicitly allowed by the target metric profile.
    allowed_ids = set(profile.get("candidate_relationships", []))
    candidates = [item for item in candidates if item["relation_id"] in allowed_ids]
    candidates.sort(key=lambda item: item["priority"], reverse=True)
    return {
        "baseline_comparisons": comparisons,
        "insight_candidates": candidates,
        "selection_policy": {
            "max_candidates_for_llm": 3,
            "ranking": [
                "relevance_to_query",
                "evidence_strength",
                "noticeable_change",
                "information_gain",
                "data_confidence",
                "safety_risk",
            ],
            "allow_empty": True,
        },
    }


def build_sleep_insights(full):
    night = full.get("night") or {}
    baseline = full.get("baseline_7d") or {}
    candidates = []

    duration = night.get("total_sleep_duration")
    baseline_duration = baseline.get("total_sleep_duration")
    if duration is not None and baseline_duration is not None:
        delta_minutes = round((duration - baseline_duration) / 60)
        direction = "多" if delta_minutes >= 0 else "少"
        candidates.append({
            "id": "duration_vs_baseline",
            "fact": f"总睡眠比近7次平均{direction}约{abs(delta_minutes)}分钟",
            "priority": 0.95,
            "related_metrics": ["total_sleep_duration"],
            "evidence": {
                "night_seconds": duration,
                "baseline_seconds": baseline_duration,
                "delta_minutes": delta_minutes,
            },
        })

    awake = night.get("awake_time")
    baseline_awake = baseline.get("awake_time")
    if awake is not None and baseline_awake is not None:
        delta_minutes = round((awake - baseline_awake) / 60)
        direction = "多" if delta_minutes >= 0 else "少"
        candidates.append({
            "id": "awake_time_vs_baseline",
            "fact": f"夜间清醒总时长比近7次平均{direction}约{abs(delta_minutes)}分钟",
            "priority": 0.82,
            "related_metrics": ["awake_time", "total_sleep_duration"],
            "evidence": {
                "night_seconds": awake,
                "baseline_seconds": baseline_awake,
                "delta_minutes": delta_minutes,
            },
        })

    efficiency = night.get("efficiency")
    baseline_efficiency = baseline.get("efficiency")
    if efficiency is not None and baseline_efficiency is not None:
        delta = round(efficiency - baseline_efficiency, 1)
        direction = "高" if delta >= 0 else "低"
        candidates.append({
            "id": "efficiency_vs_baseline",
            "fact": f"睡眠效率比近7次平均{direction}{abs(delta):g}个百分点",
            "priority": 0.75,
            "related_metrics": ["efficiency"],
            "evidence": {
                "night_percent": efficiency,
                "baseline_percent": baseline_efficiency,
                "delta_percentage_points": delta,
            },
        })

    hrv = night.get("average_hrv")
    baseline_hrv = baseline.get("average_hrv")
    if hrv is not None and baseline_hrv is not None:
        delta = round(hrv - baseline_hrv, 1)
        direction = "高" if delta >= 0 else "低"
        candidates.append({
            "id": "hrv_vs_baseline",
            "fact": f"平均HRV比近7次平均{direction}{abs(delta):g}ms",
            "priority": 0.6,
            "related_metrics": ["average_hrv"],
            "evidence": {
                "night_ms": hrv,
                "baseline_ms": baseline_hrv,
                "delta_ms": delta,
            },
        })

    return sorted(candidates, key=lambda item: item["priority"], reverse=True)


def build_p01_coach_payload(metric_result, full, response_depth):
    metric = metric_result["metric"]
    value = metric_result["night"][metric]
    direct_answer = {
        "metric": metric,
        "metric_label": metric_result["metric_label"],
        "raw_value": value,
        "unit": metric_result["unit"],
        "display_value": display_metric(metric, value, metric_result["unit"]),
    }
    candidates = build_sleep_insights(full)
    related = [
        item for item in candidates
        if metric in item["related_metrics"]
    ]
    selected = related[:2]
    claim = load_health_claims()[0]
    return {
        "response_depth": response_depth,
        "direct_answer": direct_answer,
        "selected_insights": selected,
        "allowed_action": {
            "claim_id": claim["id"],
            "text": claim["allowed_text"],
        } if response_depth == "coach" else None,
        "follow_up": {
            "type": "bedtime_commitment",
            "question": "今晚你打算几点上床？",
        } if response_depth == "coach" else None,
        "prohibited_claims": claim["prohibited_claims"],
    }
