"""Reproducible synthetic fixture generator; no production accuracy claim."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path


def main():
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    records = []
    for i in range(240):
        dangerous = bool(i % 2)
        records.append({"task_id": f"synthetic-{i}", "started_at": (start+timedelta(hours=i*2)).isoformat(),
                        "finished_at": (start+timedelta(hours=i*2+1)).isoformat(), "failed": dangerous,
                        "plan_recorded_at": (start+timedelta(hours=i*2)).isoformat(),
                        "outcome_recorded_at": (start+timedelta(hours=i*2+1)).isoformat(),
                        "plan": {"goal": "Synthetic test", "acceptance": ["Result recorded"],
                                 "steps": [{"id": "one", "description": "deploy production" if dangerous else "inspect local configuration"}]},
                        "tools_used": [], "failure_type": "synthetic_only" if dangerous else ""})
    destination = Path(__file__).resolve().parents[1] / "examples" / "history.synthetic.json"
    destination.write_text(json.dumps(records, indent=2)+"\n", encoding="utf-8")


if __name__ == "__main__":
    main()
