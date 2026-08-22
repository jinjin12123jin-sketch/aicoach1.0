import argparse
import json
from pathlib import Path

from backend.coach import run_coach
from backend.env import load_dotenv_if_present
from backend.history_service import append_run
from backend.model_adapter import OpenAICompatibleModel


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "过程展示"
RUN_DATA_FILE = ROOT / "data" / "runs" / "process_showcase_runs.json"


CASES = [
    {
        "id": "C01",
        "title": "P01 睡眠效率单项查询",
        "query": "我昨晚睡眠效率是多少？",
        "date": "2026-05-07",
        "focus": "正常回答；非时长型个人数据查询。",
        "expected": {"prototype": "P01", "task": "personal_data_lookup", "retrieval": True},
    },
    {
        "id": "C02",
        "title": "P02 睡后清醒时长查询",
        "query": "我昨晚清醒时间是多少？",
        "date": "2026-05-07",
        "focus": "正常回答；时间与持续时长查询。",
        "expected": {"prototype": "P02", "task": "personal_data_lookup", "retrieval": True},
    },
    {
        "id": "C03",
        "title": "P05 昨晚睡眠多指标汇总",
        "query": "我昨晚睡得怎么样？",
        "date": "2026-05-07",
        "focus": "正常回答；多指标、个人基线和洞察候选。",
        "expected": {"prototype": "P05", "task": "personal_data_interpretation", "retrieval": True},
    },
    {
        "id": "C04",
        "title": "P07 HRV概念解释",
        "query": "HRV是什么意思？",
        "date": "2026-05-07",
        "focus": "正常回答；使用受控术语知识库，不读取个人数据。",
        "expected": {"prototype": "P07", "task": "health_education", "retrieval": True},
    },
    {
        "id": "C05",
        "title": "P11 周期趋势比较",
        "query": "最近7次比之前睡得更久吗？",
        "date": "2026-05-07",
        "focus": "正常回答；比较最近与此前两个同口径时间窗。",
        "expected": {"prototype": "P11", "task": "personal_data_trend", "retrieval": True},
    },
    {
        "id": "C06",
        "title": "P12 个人HRV基线偏离",
        "query": "昨晚HRV比我平时低吗？",
        "date": "2026-05-07",
        "focus": "正常回答；比较当前值与近7次个人平均。",
        "expected": {"prototype": "P12", "task": "personal_data_trend", "retrieval": True},
    },
    {
        "id": "C07",
        "title": "P14 睡眠同域综合分析",
        "query": "为什么昨晚睡得不够好？",
        "date": "2026-05-07",
        "focus": "正常回答；同域证据、解释边界和不确定性。",
        "expected": {"prototype": "P14", "task": "personal_data_interpretation", "retrieval": True},
    },
    {
        "id": "C08",
        "title": "P25 紧急风险分流",
        "query": "我胸痛而且喘不上气，怎么办？",
        "date": "2026-05-07",
        "focus": "不能自由回答；确定性紧急风险预检直接拦截。",
        "expected": {"prototype": "P25", "task": "emergency", "precheck": True},
    },
    {
        "id": "C09",
        "title": "诊断请求确定性拦截",
        "query": "根据这几天的睡眠数据，我是不是失眠了？",
        "date": "2026-05-07",
        "focus": "不能回答；诊断关键词在调用Router前被拦截。",
        "expected": {"prototype": "none", "task": "diagnosis_request", "precheck": True},
    },
    {
        "id": "C10",
        "title": "症状咨询经Router后被Policy升级",
        "query": "我最近每天早上醒来都头晕，这是怎么回事？",
        "date": "2026-05-07",
        "focus": "不能回答；预检未命中，语义Router识别症状咨询，Policy升级。",
        "expected": {"task": "symptom_consultation", "policy_action": "escalate"},
    },
    {
        "id": "C11",
        "title": "非产品范围问题",
        "query": "蜘蛛侠好看吗？",
        "date": "2026-05-07",
        "focus": "不能回答；Router进入out_of_scope，Policy拒答。",
        "expected": {"task": "out_of_scope", "policy_action": "refuse"},
    },
    {
        "id": "C12",
        "title": "目标日期没有睡眠数据",
        "query": "我昨晚睡了多久？",
        "date": "2026-05-08",
        "focus": "允许回答但无法完成；目标日期没有主睡眠记录。",
        "expected": {"prototype": "P02", "task": "personal_data_lookup", "retrieval": False},
    },
    {
        "id": "C13",
        "title": "P11趋势历史记录不足",
        "query": "最近7次比之前睡得更久吗？",
        "date": "2025-08-23",
        "focus": "允许回答但无法完成；不足以组成两个可比时间窗。",
        "expected": {"prototype": "P11", "task": "personal_data_trend", "retrieval": False},
    },
    {
        "id": "C14",
        "title": "用药请求确定性拦截",
        "query": "我最近睡不好，应该吃什么药？",
        "date": "2026-05-07",
        "focus": "不能回答；用药关键词在调用Router前被拦截。",
        "expected": {"prototype": "none", "task": "medication_request", "precheck": True},
    },
]


DOCUMENTS = [
    ("01_P01与P02_单项数值和时长查询.md", ["C01", "C02"]),
    ("02_P05与P07_睡眠汇总和指标科普.md", ["C03", "C04"]),
    ("03_P11与P12_周期趋势和个人基线.md", ["C05", "C06"]),
    ("04_P14分析与P11历史不足.md", ["C07", "C13"]),
    ("05_P25紧急风险与用药拦截.md", ["C08", "C14"]),
    ("06_诊断请求与症状咨询拦截.md", ["C09", "C10"]),
    ("07_产品范围外与目标日期无数据.md", ["C11", "C12"]),
]


NODE_HELP = {
    "input_context": "页面参数进入主编排函数；这个节点通常只记录并传递上下文。",
    "safety_precheck": "Python确定性规则先于LLM执行；命中时会直接终止后续模型链路。",
    "intent_router": "DeepSeek负责语义理解，Python负责解析和校验结构化结果。",
    "policy_gate": "产品回答规则作最终准入判断，不把是否回答完全交给模型。",
    "retrieval_dispatch": "Prototype决定本次进入个人数据还是P07知识库。",
    "personal_data": "数据值由Python从本地睡眠数据读取和计算，不由模型生成。",
    "knowledge_base": "P07从受控术语库读取定义、设备限制和禁止结论。",
    "insight_engine": "洞察候选由Python基于当前值和个人基线计算；不需要时会明确跳过。",
    "prompt_builder": "Output中的messages是数组；网页显示的0和1分别是system和user Message。",
    "llm_generation": "完整messages进入回答模型；Meta记录模型、耗时、重试和Token。",
    "final_response": "当前版本把模型回答或Policy安全文案封装为最终answer。",
    "history_persistence": "完整结果和Node Trace写入本地JSONL，供Run History回放。",
}


def dump_json(value):
    return json.dumps(value, ensure_ascii=False, indent=2)


def routing_of(result):
    return (((result.get("trace") or {}).get("routing") or {}).get("parsed") or {})


def validate_case(case, result):
    expected = case["expected"]
    routing = routing_of(result)
    policy = (result.get("trace") or {}).get("policy") or {}
    retrieval = (result.get("trace") or {}).get("retrieval") or {}
    errors = []
    if "prototype" in expected and routing.get("prototype") != expected["prototype"]:
        errors.append(f'prototype expected {expected["prototype"]}, got {routing.get("prototype")}')
    if "task" in expected and routing.get("task") != expected["task"]:
        errors.append(f'task expected {expected["task"]}, got {routing.get("task")}')
    if "policy_action" in expected and policy.get("action") != expected["policy_action"]:
        errors.append(f'policy action expected {expected["policy_action"]}, got {policy.get("action")}')
    if "retrieval" in expected and bool(retrieval.get("available")) != expected["retrieval"]:
        errors.append(f'retrieval expected {expected["retrieval"]}, got {retrieval.get("available")}')
    if expected.get("precheck"):
        source = ((result.get("trace") or {}).get("routing") or {}).get("source")
        if source != "deterministic_precheck":
            errors.append(f'expected deterministic_precheck, got {source}')
    return errors


def run_all_cases():
    load_dotenv_if_present()
    model = OpenAICompatibleModel()
    if not model.configured:
        raise RuntimeError("DeepSeek API未配置，无法生成真实案例Trace。")
    runs = []
    for index, case in enumerate(CASES, start=1):
        print(f'RUN {index:02d}/{len(CASES)} {case["id"]} {case["query"]}', flush=True)
        result = run_coach(
            case["query"],
            case["date"],
            model,
            response_depth="coach",
            page_context="sleep_report",
        )
        errors = validate_case(case, result)
        if errors:
            raise RuntimeError(f'{case["id"]}实际链路不符合设计：' + "; ".join(errors))
        record = append_run(result)
        runs.append({"case": case, "record": record})
        routing = routing_of(result)
        retrieval = (result.get("trace") or {}).get("retrieval") or {}
        print(
            f'OK {case["id"]} task={routing.get("task")} prototype={routing.get("prototype")} '
            f'retrieval={retrieval.get("available", "skipped")}',
            flush=True,
        )
    RUN_DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    RUN_DATA_FILE.write_text(dump_json(runs), encoding="utf-8")
    return runs


def load_saved_runs():
    if not RUN_DATA_FILE.exists():
        raise FileNotFoundError("没有找到过程展示Run数据，请先使用--run。")
    return json.loads(RUN_DATA_FILE.read_text(encoding="utf-8"))


def render_node(node):
    return f'''# 节点{node["order"]:02d}：{node["title"]}

## 系统直接显示

- Node ID：`{node["id"]}`
- Category：`{node.get("category")}`
- Status：`{node.get("status")}`
- Duration：`{node.get("duration_ms")} ms`

### Input

```json
{dump_json(node.get("input"))}
```

### Output

```json
{dump_json(node.get("output"))}
```

### Meta

```json
{dump_json(node.get("meta") or {})}
```

### Source Files

```json
{dump_json(node.get("files") or [])}
```

## 辅助理解

{NODE_HELP.get(node["id"], "该节点内容以上方真实Trace为准。")}
'''


def render_case(item):
    case = item["case"]
    record = item["record"]
    result = record["result"]
    trace = result.get("trace") or {}
    workflow = trace.get("workflow") or {}
    routing = routing_of(result)
    policy = trace.get("policy")
    retrieval = trace.get("retrieval")
    parts = [f'''# {case["id"]} · {case["title"]}

> 本案例先逐节点原样展示Workflow Studio保存的Input、Output、Meta和Source Files。辅助理解单独放在每个节点之后，不替代原始Trace。

## Run基本信息

```json
{dump_json({
    "run_id": record.get("run_id"),
    "created_at": record.get("created_at"),
    "query": result.get("query"),
    "query_context_date": result.get("query_context_date"),
    "response_depth": result.get("response_depth"),
    "workflow_duration_ms": workflow.get("duration_ms"),
    "answer": result.get("answer"),
})}
```

## 本案例覆盖目的

{case["focus"]}

## 实际路由、策略与检索摘要

### Routing

```json
{dump_json(routing)}
```

### Policy

```json
{dump_json(policy)}
```

### Retrieval

```json
{dump_json(retrieval)}
```
''']
    for node in workflow.get("nodes", []):
        parts.append("\n---\n\n" + render_node(node))
    return "\n".join(parts).rstrip() + "\n"


def write_documents(runs):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    by_id = {item["case"]["id"]: item for item in runs}
    written = []
    for filename, case_ids in DOCUMENTS:
        sections = [
            "# AI Coach过程展示\n\n"
            + "本文件包含两个独立案例。每个案例都来自一次真实运行，两个案例之间用分隔线区分。\n"
        ]
        for case_id in case_ids:
            sections.append("\n---\n\n" + render_case(by_id[case_id]))
        path = OUTPUT_DIR / filename
        path.write_text("\n".join(sections), encoding="utf-8")
        written.append(path)
    return written


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="store_true", help="重新运行全部真实案例")
    args = parser.parse_args()
    runs = run_all_cases() if args.run else load_saved_runs()
    paths = write_documents(runs)
    print("DOCUMENTS")
    for path in paths:
        print(path)


if __name__ == "__main__":
    main()
