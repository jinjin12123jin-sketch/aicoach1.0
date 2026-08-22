import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_FILE = ROOT / "config" / "prototypes.json"


def load_prototypes():
    return json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))


def get_prototype(prototype_id):
    return next(
        (item for item in load_prototypes() if item["id"] == prototype_id),
        None,
    )


def supported_metric_names():
    names = set()
    for item in load_prototypes():
        names.update(item.get("supported_metrics", []))
    return names
