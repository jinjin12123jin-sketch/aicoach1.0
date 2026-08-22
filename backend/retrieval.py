from .answer_planner import get_p02_metric_profile
from .data_service import (
    METRIC_METADATA,
    P02_CONTEXT_METADATA,
    get_night_and_baseline,
    get_p02_context,
    get_period_comparison,
    get_single_metric,
)
from .insight_engine import (
    build_p01_coach_payload,
    build_sleep_insights,
    display_metric,
    display_p02_value,
)
from .knowledge_service import find_sleep_term


def retrieve_for_route(query_context_date, routing, response_depth="coach"):
    prototype = routing.get("prototype")
    parameters = routing.get("parameters") or {}

    if prototype == "P01":
        metric = parameters.get("metric")
        if not metric:
            return {
                "available": False,
                "reason": "单指标查询缺少 metric 参数",
            }
        full = get_night_and_baseline(query_context_date)
        if not full.get("available"):
            return full
        result = get_single_metric(query_context_date, metric, full=full)
        if result.get("available"):
            result["coach_payload"] = build_p01_coach_payload(
                result,
                full,
                response_depth,
            )
        return result

    if prototype == "P02":
        metric = parameters.get("metric")
        if not metric:
            return {"available": False, "reason": "时间点与时长查询缺少 metric 参数"}
        profile = get_p02_metric_profile(metric)
        result = get_p02_context(
            query_context_date,
            metric,
            baseline_n=profile["baseline_sessions"],
        )
        if not result.get("available"):
            return result

        current_facts = {}
        for field, value in result["current"].items():
            if value is None or field not in P02_CONTEXT_METADATA:
                continue
            metadata = P02_CONTEXT_METADATA[field]
            current_facts[field] = {
                "available": True,
                "metric": field,
                "label": metadata["label"],
                "raw_value": value,
                "unit": metadata["unit"],
                "display_value": display_p02_value(field, value, metadata["unit"]),
            }

        computed_facts = {}
        total_sleep = result["current"].get("total_sleep_duration")
        for stage_metric, computed_id, label in (
            ("deep_sleep_duration", "deep_sleep_share", "深睡占总睡眠比例"),
            ("rem_sleep_duration", "rem_sleep_share", "REM占总睡眠比例"),
        ):
            stage_value = result["current"].get(stage_metric)
            if stage_value is not None and total_sleep and total_sleep > 0:
                share = round(float(stage_value) / float(total_sleep) * 100)
                computed_facts[computed_id] = {
                    "available": True,
                    "metric": computed_id,
                    "label": label,
                    "raw_value": share,
                    "unit": "percent",
                    "display_value": f"{share}%",
                    "calculation": f"{stage_metric} / total_sleep_duration",
                }

        time_in_bed = result["current"].get("time_in_bed")
        if time_in_bed is not None and total_sleep is not None and time_in_bed >= total_sleep:
            gap = float(time_in_bed) - float(total_sleep)
            computed_facts["non_sleep_gap"] = {
                "available": True,
                "metric": "non_sleep_gap",
                "label": "卧床时长与实际睡眠的差值",
                "raw_value": gap,
                "unit": "seconds",
                "display_value": display_metric("non_sleep_gap", gap, "seconds"),
                "calculation": "time_in_bed - total_sleep_duration",
                "limit": "该差值不直接等同于夜醒次数或某一种睡眠问题。",
            }

        result["metric_profile"] = profile
        result["current_facts"] = current_facts
        result["computed_facts"] = computed_facts
        result["display_value"] = current_facts[metric]["display_value"]
        return result

    if prototype == "P07":
        return find_sleep_term(parameters.get("term"), routing.get("query"))

    if prototype == "P11":
        window_n = int(parameters.get("window_sessions", 7))
        window_n = min(max(window_n, 2), 28)
        return get_period_comparison(
            query_context_date,
            parameters.get("metric"),
            window_n,
        )

    if prototype == "P12":
        metric = parameters.get("metric")
        full = get_night_and_baseline(query_context_date)
        if not full.get("available"):
            return full
        current = (full.get("night") or {}).get(metric)
        baseline = (full.get("baseline_7d") or {}).get(metric)
        if current is None or baseline is None:
            return {"available": False, "reason": "当前值或个人基线不可用"}
        unit = get_single_metric(query_context_date, metric, full=full)["unit"]
        delta = current - baseline
        return {
            "available": True,
            "query_context_date": query_context_date,
            "metric": metric,
            "unit": unit,
            "current": current,
            "current_display": display_metric(metric, current, unit),
            "baseline_7_sessions": baseline,
            "baseline_display": display_metric(metric, baseline, unit),
            "delta": delta,
            "direction": "higher" if delta > 0 else "lower" if delta < 0 else "stable",
            "limit": "当前Demo只比较平均基线，尚未计算个人常见波动区间。",
        }

    if prototype == "P05":
        result = get_night_and_baseline(query_context_date)
        if result.get("available"):
            result["insight_candidates"] = build_sleep_insights(result)
        return result

    if prototype == "P14":
        result = get_night_and_baseline(query_context_date)
        if result.get("available"):
            result["insight_candidates"] = build_sleep_insights(result)
            result["display_night"] = {
                metric: display_metric(metric, value, METRIC_METADATA[metric]["unit"])
                for metric, value in result["night"].items()
                if value is not None and metric in METRIC_METADATA
            }
            result["display_baseline_7d"] = {
                metric: display_metric(metric, value, METRIC_METADATA[metric]["unit"])
                for metric, value in result["baseline_7d"].items()
                if value is not None and metric in METRIC_METADATA
            }
            result["analysis_limit"] = (
                "只允许基于同一晚睡眠数据和个人基线提出可能解释；"
                "不得诊断失眠、把相关性写成病因，或列举输入中没有的具体影响因素。"
            )
        return result

    return {
        "available": False,
        "reason": f"暂未实现原型 {prototype} 的数据检索",
    }
