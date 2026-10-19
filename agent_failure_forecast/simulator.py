"""Static rehearsal only."""
from .scanner import scan


def simulate(root, plan):
    result = scan(root, plan)
    result["simulation"] = {"kind": "static", "executed_steps": 0, "external_calls": 0}
    return result
