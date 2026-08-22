import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
HISTORY_FILE = ROOT / "data" / "runs" / "history.jsonl"


def append_run(result):
    run_id = str(uuid4())
    created_at = datetime.now().astimezone().isoformat(timespec="seconds")
    workflow = (result.get("trace") or {}).get("workflow") or {}
    for node in workflow.get("nodes", []):
        if node.get("id") == "history_persistence":
            node.update({
                "status": "success",
                "started_at": created_at,
                "ended_at": created_at,
                "duration_ms": 0.0,
                "input": {"storage": "data/runs/history.jsonl"},
                "output": {"run_id": run_id, "created_at": created_at},
            })
    record = {
        "run_id": run_id,
        "created_at": created_at,
        "result": result,
    }
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def load_runs(limit=200):
    if not HISTORY_FILE.exists():
        return []
    records = []
    for line in HISTORY_FILE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return list(reversed(records[-limit:]))
