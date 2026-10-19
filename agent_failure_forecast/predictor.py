"""Small auditable logistic model with disjoint sigmoid calibration."""
from datetime import datetime, timezone
import hashlib
import json
import math
from .features import extract, FEATURE_NAMES
from .planner import normalize

MODEL_VERSION = "logistic-sigmoid-v2"
MIN_SAMPLES = 120


def sigmoid(z):
    return 1/(1+math.exp(-max(-35, min(35, z))))


def fit(xs, ys, epochs=600):
    weights = [0.0] * (len(xs[0])+1)
    for _ in range(epochs):
        gradient = [0.0]*len(weights)
        for x, y in zip(xs, ys):
            row = [1.0]+x
            error = sigmoid(sum(a*b for a, b in zip(weights, row)))-y
            for j, value in enumerate(row):
                gradient[j] += error*value/len(xs)
        weights = [w-0.3*(g+(0.002*w if j else 0)) for j, (w, g) in enumerate(zip(weights, gradient))]
    return weights


def score(weights, x):
    return sum(a*b for a, b in zip(weights, [1.0]+x))


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError("timestamps must be ISO 8601 strings")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("invalid timestamp") from None
    if dt.tzinfo is None:
        raise ValueError("timestamps must include timezone")
    try:
        return dt.astimezone(timezone.utc)
    except (OverflowError, ValueError):
        raise ValueError("timestamp outside supported UTC range") from None


def validate_history(records):
    if not isinstance(records, list) or len(records) > 10000:
        raise ValueError("history must be an array of at most 10000 records")
    seen = set()
    for r in records:
        if not isinstance(r, dict) or not isinstance(r.get("task_id"), str) or not r["task_id"] or r["task_id"] in seen:
            raise ValueError("history needs unique task_id values")
        seen.add(r["task_id"])
        start, end = timestamp(r.get("started_at")), timestamp(r.get("finished_at"))
        if end < start or type(r.get("failed")) is not bool:
            raise ValueError("invalid execution interval or failed label")
        if "plan_recorded_at" in r and timestamp(r["plan_recorded_at"]) > start:
            raise ValueError("plan snapshot must be recorded before execution")
        if "outcome_recorded_at" in r and timestamp(r["outcome_recorded_at"]) < end:
            raise ValueError("outcome cannot be recorded before completion")
        if "group_id" in r and (not isinstance(r["group_id"], str) or not r["group_id"]):
            raise ValueError("group_id must be a nonempty string")
        if not isinstance(r.get("plan"), dict):
            raise ValueError("historical plan snapshot must be a JSON object")
        normalize(r["plan"])
        if not isinstance(r.get("tools_used", []), list) or any(not isinstance(x, str) for x in r.get("tools_used", [])) or not isinstance(r.get("failure_type", ""), str):
            raise ValueError("invalid execution metadata")
    return sorted(records, key=lambda r: timestamp(r["started_at"]))


def brier(ys, ps):
    return sum((y-p)**2 for y, p in zip(ys, ps))/len(ys)


def evaluate(records):
    records = validate_history(records)
    fallback = {"eligible": False, "model_version": MODEL_VERSION, "samples": len(records), "reason": "insufficient_history", "failure_probability": None}
    if len(records) < MIN_SAMPLES:
        return fallback, None
    if any("plan_recorded_at" not in r or "outcome_recorded_at" not in r for r in records):
        return dict(fallback, reason="unverified_history_provenance"), None
    if any("group_id" in r for r in records) and any("group_id" not in r for r in records):
        return dict(fallback, reason="incomplete_group_metadata"), None
    a, b, c = int(len(records)*0.5), int(len(records)*0.7), int(len(records)*0.85)
    train, calibration, selection, test = records[:a], records[a:b], records[b:c], records[c:]
    blocks = (train, calibration, selection, test)
    # Test labels are used only for reporting, never eligibility or fitting.
    for part in (train, calibration, selection):
        if sum(r["failed"] for r in part) < 5 or sum(not r["failed"] for r in part) < 5:
            return dict(fallback, reason="insufficient_class_support"), None
    # All labels in a fitting block must be known before the next block starts.
    for earlier, later in zip(blocks, blocks[1:]):
        if max(timestamp(r["outcome_recorded_at"]) for r in earlier) >= timestamp(later[0]["started_at"]):
            return dict(fallback, reason="overlapping_time_blocks"), None
    groups = [set(r["group_id"] for r in part if "group_id" in r) for part in blocks]
    if any(groups[i] & groups[j] for i in range(4) for j in range(i+1, 4)):
        return dict(fallback, reason="group_overlap_between_blocks"), None
    xs = lambda rows: [extract(r["plan"]) for r in rows]
    ys = lambda rows: [int(r["failed"]) for r in rows]
    weights = fit(xs(train), ys(train))
    calibrator = fit([[score(weights, x)] for x in xs(calibration)], ys(calibration))
    raw = [sigmoid(score(weights, x)) for x in xs(test)]
    ps = [sigmoid(score(calibrator, [score(weights, x)])) for x in xs(test)]
    baseline = sum(ys(train))/len(train)
    selected_ps = [sigmoid(score(calibrator, [score(weights, x)])) for x in xs(selection)]
    selection_quality = {"calibrated_brier": brier(ys(selection), selected_ps), "baseline_brier": brier(ys(selection), [baseline]*len(selection))}
    quality = {"raw_brier": brier(ys(test), raw), "calibrated_brier": brier(ys(test), ps), "baseline_brier": brier(ys(test), [baseline]*len(test)), "calibration_bins": [], "role": "untouched_test"}
    for i in range(5):
        pairs = [(p, y) for p, y in zip(ps, ys(test)) if i/5 <= p < (i+1)/5]
        if pairs:
            quality["calibration_bins"].append({"count": len(pairs), "mean_probability": sum(p for p, _ in pairs)/len(pairs), "observed_failure_rate": sum(y for _, y in pairs)/len(pairs)})
    eligible = selection_quality["calibrated_brier"] < selection_quality["baseline_brier"]
    # Model identity depends on fitted parameters, not held-out outcome labels.
    digest = hashlib.sha256(json.dumps([weights, calibrator, FEATURE_NAMES], sort_keys=True).encode()).hexdigest()[:12]
    data_version = hashlib.sha256(json.dumps(records, sort_keys=True).encode()).hexdigest()[:12]
    metadata = {"eligible": eligible, "model_version": MODEL_VERSION+"-"+digest, "samples": len(records),
                "data_version": data_version,
                "split_samples": {"train": len(train), "calibration": len(calibration), "selection": len(selection), "test": len(test)},
                "boundaries": {"train_end": train[-1]["started_at"], "calibration_start": calibration[0]["started_at"], "calibration_end": calibration[-1]["started_at"], "selection_start": selection[0]["started_at"], "selection_end": selection[-1]["started_at"], "test_start": test[0]["started_at"], "test_end": max(timestamp(r["outcome_recorded_at"]) for r in test).isoformat()},
                "features": list(FEATURE_NAMES), "selection_quality": selection_quality, "quality": quality, "reason": "passed_selection_gate" if eligible else "not_better_than_baseline",
                "limitations": ["Retrospective selection is not evidence of prospective accuracy; the test block does not select or fit the model.", "Known group IDs are isolated; undisclosed task families and distribution shift need external validation.", "Provenance timestamps are declarations, not authenticated proof.", "Calibration bins have sampling uncertainty; no accuracy guarantee."]}
    return metadata, (weights, calibrator)


def predict(plan, records, as_of=None):
    as_of = timestamp(as_of) if as_of else datetime.now(timezone.utc)
    records = validate_history(records)
    available = [r for r in records if timestamp(r.get("outcome_recorded_at", r["finished_at"])) < as_of]
    metadata, model = evaluate(available)
    if metadata["eligible"]:
        weights, calibrator = model
        probability = sigmoid(score(calibrator, [score(weights, extract(plan))]))
    else:
        probability = None
    return {"mode": "statistical" if probability is not None else "rules", "failure_probability": probability,
            "as_of": as_of.isoformat(), "excluded_future_records": len(records)-len(available), "model": metadata}
