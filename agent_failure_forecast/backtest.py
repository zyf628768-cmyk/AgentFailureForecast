"""Expanding chronological backtests; each test window is unseen by fitting."""
from .predictor import evaluate, validate_history


def backtest(records):
    records = validate_history(records)
    # Each evaluation uses an expanding train/calibration prefix and trailing holdout.
    endpoints = sorted(set([int(len(records)*0.6), int(len(records)*0.8), len(records)]))
    folds = [evaluate(records[:end])[0] for end in endpoints if end]
    return {"schema_version": "1.0", "kind": "expanding_chronological", "samples": len(records), "folds": folds,
            "warning": "Later folds may reuse earlier holdouts in training. Do not treat fold metrics as independent or tune on them."}
