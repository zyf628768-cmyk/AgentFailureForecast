"""All planned commands remain inert. Only explicit --output writes a report."""
import argparse
import json
from pathlib import Path
import sys
from . import __version__
from .backtest import backtest
from .planner import build_graph
from .predictor import predict
from .report import render
from .safety import load_json, read_text, write_report
from .scanner import scan
from .simulator import simulate


def parser():
    cli = argparse.ArgumentParser(prog="forecast", description="Offline read-only static agent preflight. No planned command is executed.")
    cli.add_argument("--version", action="version", version=__version__)
    commands = cli.add_subparsers(dest="command", required=True)
    for name, description in [("scan", "Analyze risks and local prerequisites"), ("plan", "Validate dependencies and emit a JSON graph"), ("simulate", "Statically rehearse without executing steps"), ("predict", "Evaluate history; predict only when eligible"), ("backtest", "Evaluate chronological historical holdouts"), ("report", "Render an existing JSON analysis")]:
        cmd = commands.add_parser(name, help=description, description=description)
        if name in ("scan", "plan", "simulate", "predict"):
            cmd.add_argument("--plan", required=True, help="Explicitly selected JSON or plain .txt plan file")
            cmd.add_argument("--root", default=".", help="Workspace boundary; default current directory")
            cmd.add_argument("--fail-on", choices=("low", "medium", "high", "critical"), help="Exit 3 after writing the report if a finding meets this severity or higher")
        if name in ("predict", "backtest"):
            cmd.add_argument("--history", required=name == "backtest", help="Local JSON array of historical records")
        if name == "predict":
            cmd.add_argument("--as-of", help="ISO timestamp; exclude outcomes not yet known at this instant")
        if name == "report":
            cmd.add_argument("--input", required=True, help="Previously generated JSON report")
        cmd.add_argument("--format", choices=("json", "markdown", "html"), default="json")
        cmd.add_argument("--output", help="Explicit destination; fails if file exists (use --force to replace)")
        cmd.add_argument("--force", action="store_true", help="Authorize replacement of an existing output file")
    return cli


def main(argv=None):
    args = parser().parse_args(argv)
    # JSON/stdout is UTF-8 on every platform, including legacy Windows pipes.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        if args.command in ("scan", "plan", "simulate", "predict"):
            plan = read_text(args.plan) if Path(args.plan).suffix.lower() == ".txt" else load_json(args.plan)
        if args.command == "plan":
            result = build_graph(plan)
        elif args.command == "scan":
            result = scan(args.root, plan)
        elif args.command == "simulate":
            result = simulate(args.root, plan)
        elif args.command == "predict":
            result = scan(args.root, plan)
            result.update(predict(plan, load_json(args.history) if args.history else [], args.as_of))
        elif args.command == "backtest":
            result = backtest(load_json(args.history))
        else:
            result = load_json(args.input)
            if not isinstance(result, dict):
                raise ValueError("report input must be a JSON object")
        output = render(result, args.format)
        if args.output:
            write_report(args.output, output, args.force)
        else:
            sys.stdout.write(output)
        threshold = getattr(args, "fail_on", None)
        levels = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        if threshold and any(levels[f["severity"]] >= levels[threshold] for f in result.get("findings", [])):
            return 3
        return 0
    except (ValueError, OSError, UnicodeError, RecursionError) as error:
        # Error details may contain user-supplied secrets or filesystem contents.
        sys.stderr.write("forecast: invalid or inaccessible input/output (" + type(error).__name__ + "); verify schema, paths and encoding.\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
