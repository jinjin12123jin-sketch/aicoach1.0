
import argparse

from backend.env import load_dotenv_if_present
from backend.model_adapter import OpenAICompatibleModel
from backend.coach import run_coach
from backend.evaluator import load_case, run_eval

load_dotenv_if_present()
parser = argparse.ArgumentParser(description="运行单条 AI Coach Bench Case")
parser.add_argument("--case-id", default="SLEEP_P05_001")
args = parser.parse_args()
model = OpenAICompatibleModel()
case = load_case(args.case_id)
r = run_coach(case["model_input"]["query"], case["model_input"]["query_context_date"], model)
print("ANSWER:", r["answer"])
print(run_eval(
    case,
    r["answer"],
    r["trace"]["routing"]["parsed"],
    model,
    r["trace"].get("retrieval"),
))
