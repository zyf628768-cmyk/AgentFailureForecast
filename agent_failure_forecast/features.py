"""Only pre-execution features. No outcome or free-form text features."""
from .planner import normalize
from .rules import analyze_text

FEATURE_NAMES = ("steps", "dangerous", "network", "missing_acceptance", "tools")


def extract(plan):
    plan = normalize(plan)
    steps = plan.get("steps", [])
    risks = analyze_text(plan.get("goal", "") + " " + " ".join(s.get("description", "") for s in steps))
    return [min(len(steps), 50)/50, float(any(r["requires_approval"] for r in risks)),
            float(any(r["id"] == "NET001" for r in risks)), float(not plan.get("acceptance")),
            min(sum(len(s.get("tools", [])) for s in steps), 20)/20]
