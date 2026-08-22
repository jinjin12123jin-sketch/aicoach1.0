import copy
import json
from datetime import datetime
from pathlib import Path
from time import perf_counter


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_FILE = ROOT / "config" / "workflow_modules.json"
SENSITIVE_KEYS = {"api_key", "authorization", "token", "secret", "password"}


def now_iso():
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def load_workflow_manifest():
    return json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))


def sanitize(value):
    if isinstance(value, dict):
        cleaned = {}
        for key, item in value.items():
            if str(key).lower() in SENSITIVE_KEYS:
                cleaned[key] = "[REDACTED]"
            else:
                cleaned[key] = sanitize(item)
        return cleaned
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize(item) for item in value]
    return value


class WorkflowTrace:
    def __init__(self, flow="runtime"):
        manifest = load_workflow_manifest()
        key = "runtime_nodes" if flow == "runtime" else "evaluation_nodes"
        self.flow = flow
        self.started_at = now_iso()
        self._started_perf = perf_counter()
        self.nodes = []
        for index, definition in enumerate(manifest[key]):
            self.nodes.append({
                **copy.deepcopy(definition),
                "order": index + 1,
                "status": "pending",
                "started_at": None,
                "ended_at": None,
                "duration_ms": None,
                "input": None,
                "output": None,
                "meta": {},
            })

    def node(self, node_id):
        return next(node for node in self.nodes if node["id"] == node_id)

    def start(self, node_id, input_data=None, meta=None):
        node = self.node(node_id)
        node["status"] = "running"
        node["started_at"] = now_iso()
        node["input"] = sanitize(input_data)
        node["meta"] = sanitize(meta or {})
        node["_started_perf"] = perf_counter()
        return node

    def finish(self, node_id, output=None, status="success", meta=None):
        node = self.node(node_id)
        started = node.pop("_started_perf", perf_counter())
        node["status"] = status
        node["ended_at"] = now_iso()
        node["duration_ms"] = round((perf_counter() - started) * 1000, 1)
        node["output"] = sanitize(output)
        if meta:
            node["meta"].update(sanitize(meta))
        return node

    def skip(self, node_id, reason, input_data=None):
        node = self.node(node_id)
        node["status"] = "skipped"
        node["input"] = sanitize(input_data)
        node["output"] = {"reason": reason}
        node["started_at"] = now_iso()
        node["ended_at"] = node["started_at"]
        node["duration_ms"] = 0.0
        return node

    def fail(self, node_id, error):
        return self.finish(node_id, {"error": str(error)}, status="error")

    def skip_pending(self, reason):
        for node in self.nodes:
            if node["status"] == "pending":
                self.skip(node["id"], reason)

    def as_dict(self):
        nodes = []
        for node in self.nodes:
            clean = {k: v for k, v in node.items() if not k.startswith("_")}
            nodes.append(clean)
        return {
            "schema_version": "1.0",
            "flow": self.flow,
            "started_at": self.started_at,
            "duration_ms": round((perf_counter() - self._started_perf) * 1000, 1),
            "nodes": nodes,
        }


def legacy_workflow_from_result(result):
    existing = (result.get("trace") or {}).get("workflow")
    if existing:
        return existing
    recorder = WorkflowTrace()
    recorder.finish("input_context", {
        "query": result.get("query"),
        "query_context_date": result.get("query_context_date"),
    }, meta={"legacy_run": True})
    trace = result.get("trace") or {}
    if trace.get("routing"):
        recorder.finish("intent_router", trace["routing"], meta={"legacy_run": True})
    if trace.get("policy"):
        recorder.finish("policy_gate", trace["policy"], meta={"legacy_run": True})
    if trace.get("retrieval"):
        recorder.finish("retrieval_dispatch", trace["retrieval"], meta={"legacy_run": True})
    if trace.get("generation_messages"):
        recorder.finish("prompt_builder", trace["generation_messages"], meta={"legacy_run": True})
    if trace.get("raw_generation"):
        recorder.finish("llm_generation", trace["raw_generation"], meta={"legacy_run": True})
    if result.get("answer"):
        recorder.finish("final_response", {"answer": result["answer"]}, meta={"legacy_run": True})
    recorder.skip_pending("旧版记录未保存该节点信息")
    return recorder.as_dict()


def expand_source_patterns(patterns):
    found = []
    for pattern in patterns:
        if any(char in pattern for char in "*?["):
            candidates = ROOT.glob(pattern)
        else:
            candidates = [ROOT / pattern]
        for path in candidates:
            if path.is_file():
                relative = path.relative_to(ROOT).as_posix()
                if relative not in found:
                    found.append(relative)
    return sorted(found)


def all_project_resources():
    manifest = load_workflow_manifest()
    assigned = set()
    groups = []
    for group in manifest["catalog"]:
        files = expand_source_patterns(group["files"])
        assigned.update(files)
        groups.append({**group, "resolved_files": files})
    all_files = {
        path.relative_to(ROOT).as_posix()
        for pattern in ("*.py", "*.json")
        for path in ROOT.rglob(pattern)
        if ".venv" not in path.parts and "__pycache__" not in path.parts
    }
    uncategorized = sorted(all_files - assigned)
    if uncategorized:
        groups.append({"id": "other", "title": "其他实现资源", "resolved_files": uncategorized})
    return groups


def read_project_file(relative_path):
    path = (ROOT / relative_path).resolve()
    if path != ROOT.resolve() and ROOT.resolve() not in path.parents:
        raise ValueError("文件路径越出项目目录")
    if path.name == ".env":
        raise ValueError("不允许在工作台读取.env")
    return path.read_text(encoding="utf-8", errors="replace")
