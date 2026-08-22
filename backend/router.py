
import json, re
from .prompts import router_messages
from .prototype_registry import get_prototype

def route(query, context, model):
    raw = model.chat(
        router_messages(query, context),
        temperature=0.0,
        max_tokens=500,
        json_mode=True,
        retries=2,
        thinking=False,
    )
    cleaned = re.sub(r"^```json\s*|\s*```$", "", raw.strip())
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Router 返回了无效 JSON：{exc.msg}") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("Router 返回格式错误：预期为 JSON 对象。")
    answerability_aliases = {
        "answerable": "answer",
        "can_answer": "answer",
        "unanswerable": "cannot_answer",
        "not_answerable": "cannot_answer",
    }
    parsed["answerability"] = answerability_aliases.get(
        parsed.get("answerability"),
        parsed.get("answerability"),
    )
    if parsed.get("answerability") not in {"answer", "cannot_answer"}:
        raise RuntimeError(
            f'Router 返回了未知 answerability：{parsed.get("answerability")}'
        )
    parsed.setdefault("parameters", {})
    if not isinstance(parsed["parameters"], dict):
        raise RuntimeError("Router 返回格式错误：parameters 必须是 JSON 对象。")

    if parsed.get("answerability") == "answer":
        prototype = get_prototype(parsed.get("prototype"))
        if not prototype:
            raise RuntimeError(f'Router 返回了未知原型：{parsed.get("prototype")}')
        if parsed.get("task") != prototype.get("task"):
            raise RuntimeError("Router 返回的 prototype 与 task 不一致。")
        if parsed.get("intent") != prototype["intent"]:
            raise RuntimeError("Router 返回的 prototype 与 intent 不一致。")
        if prototype.get("supported_metrics"):
            metric = parsed["parameters"].get("metric")
            if metric not in prototype.get("supported_metrics", []):
                raise RuntimeError(
                    f'Router 为 {prototype["id"]} 返回了不受支持的指标：{metric}'
                )
        if prototype.get("supported_terms"):
            term = parsed["parameters"].get("term")
            if term not in prototype.get("supported_terms", []):
                raise RuntimeError(
                    f'Router 为 {prototype["id"]} 返回了不受支持的术语：{term}'
                )
    elif not parsed.get("task"):
        parsed["task"] = "out_of_scope"
    return {"parsed": parsed, "raw": raw}
