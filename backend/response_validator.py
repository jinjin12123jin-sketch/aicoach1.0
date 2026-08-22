import re


def _display_alternatives(value):
    value = str(value)
    alternatives = {value}
    if re.fullmatch(r"0\d:\d{2}", value):
        alternatives.add(value[1:])
    return alternatives


def _contains_display(answer, value):
    return any(item in answer for item in _display_alternatives(value))


def validate_p02_response(answer, answer_plan):
    errors = []
    answer = (answer or "").strip()
    if not answer:
        return {"valid": False, "errors": ["回答为空"]}

    for metric, fact in (answer_plan.get("required_facts") or {}).items():
        display_value = fact.get("display_value")
        if display_value and not _contains_display(answer, display_value):
            errors.append(f"没有使用必答字段{metric}的展示值：{display_value}")

    if (answer_plan.get("answer_policy") or {}).get("include_default_companions"):
        for companion in answer_plan.get("default_companions") or []:
            if companion.get("type") != "fact":
                continue
            display_value = companion.get("display_value")
            if display_value and not _contains_display(answer, display_value):
                errors.append(f'没有使用默认信息{companion.get("id")}：{display_value}')

    policy = answer_plan.get("answer_policy") or {}
    for phrase in policy.get("avoid_preambles") or []:
        if phrase in answer:
            errors.append(f"出现禁止的报告腔开场：{phrase}")
    for phrase in policy.get("forbidden_claim_fragments") or []:
        if phrase in answer:
            errors.append(f"出现禁止结论：{phrase}")
    for phrase in policy.get("ungrounded_evaluation_fragments") or []:
        if phrase in answer:
            errors.append(f"出现Answer Plan未提供的状态评价：{phrase}")

    query = answer_plan.get("user_query") or ""
    relative_phrase = (answer_plan.get("query_focus") or {}).get("relative_time_phrase")
    if relative_phrase and not re.search(r"20\d{2}年", query) and re.search(r"20\d{2}年", answer):
        errors.append("用户使用相对日期时不应主动展开具体年份")

    internal_markers = (
        "source_session_id",
        "source_data_timezone_not_provided",
        "原始数据未提供时区",
        "query_context_date",
    )
    for marker in internal_markers:
        if marker in answer:
            errors.append(f"输出了内部元数据：{marker}")

    return {
        "valid": not errors,
        "errors": errors,
        "checked_rules": [
            "required_fact_grounding",
            "default_companion_grounding",
            "forbidden_preambles",
            "forbidden_claim_fragments",
            "ungrounded_evaluation_fragments",
            "relative_date_style",
            "internal_metadata_hiding",
        ],
    }
