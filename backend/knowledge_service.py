import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SLEEP_TERMS_FILE = ROOT / "config" / "knowledge" / "sleep_terms.json"


def load_sleep_terms():
    return json.loads(SLEEP_TERMS_FILE.read_text(encoding="utf-8"))


def normalize_term(value):
    return str(value or "").strip().lower().replace(" ", "")


def find_sleep_term(term=None, query=None):
    library = load_sleep_terms()
    requested = normalize_term(term)
    query_text = normalize_term(query)

    for item in library["terms"]:
        candidates = [item["id"], item["term"], *item.get("aliases", [])]
        normalized = [normalize_term(value) for value in candidates]
        if requested and requested in normalized:
            return {
                "available": True,
                "review_status": library["review_status"],
                "global_notice": library["global_notice"],
                "term_entry": item,
            }

    matches = []
    for item in library["terms"]:
        candidates = [item["term"], *item.get("aliases", [])]
        for candidate in candidates:
            token = normalize_term(candidate)
            if token and token in query_text:
                matches.append((len(token), item))
    if matches:
        item = max(matches, key=lambda pair: pair[0])[1]
        return {
            "available": True,
            "review_status": library["review_status"],
            "global_notice": library["global_notice"],
            "term_entry": item,
        }
    return {
        "available": False,
        "reason": "睡眠术语知识库中没有找到对应词条",
    }
