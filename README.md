# AgentFailureForecast

**Predict Agent Failures Before They Happen.**

An offline, read-only Python preflight engine and Agent Skill. Analyze a proposed task before execution: identify risk signals, validate declared prerequisites, inspect Git cleanliness and check the dependency graph. All six commands are implemented. No paid model key or third-party runtime dependency is required.

This is a v0.1.0 MVP. Rules are transparent heuristics, not failure probabilities. The optional historical model has been tested with synthetic data only; real-world accuracy is unverified. [中文说明](README.zh-CN.md).

## Install

Python 3.10+ and trusted system Git (optional for non-Git analysis):

```sh
git clone https://github.com/zyf628768-cmyk/AgentFailureForecast.git
cd AgentFailureForecast
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install .
forecast --help
```

Alternatively install the released wheel with `python -m pip install path/to/agent_failure_forecast-0.1.0-py3-none-any.whl`. Installation from a wheel can be fully offline with `--no-index`. Source build dependencies may need an initial download; scanning itself never accesses the network.

## Run

From this repository:

```sh
forecast scan --root . --plan examples/plan.json
forecast plan --plan examples/plan.json
forecast simulate --root . --plan examples/plan.json
forecast predict --root . --plan examples/plan.json
forecast predict --root . --plan examples/plan.json --history examples/history.synthetic.json --as-of 2026-01-01T00:00:00Z
forecast backtest --history examples/history.synthetic.json
forecast scan --root . --plan examples/plan.json --output scan.json
forecast report --input scan.json --format markdown --output report.md
forecast report --input scan.json --format html --output report.html
```

Use `python -m agent_failure_forecast` from a trusted directory in place of `forecast` if desired. `--output` refuses existing files; `--force` explicitly authorizes atomic replacement. Commands default to stdout. Exit 0 means the analysis ran, including when critical risks were found; exit 2 means invalid/inaccessible input. Add `--fail-on high` to scan/plan/simulate/predict to write the report and then exit 3 if a finding meets/exceeds that severity. No exit code proves safety.

The checked-in example report contains this actual finding (selected fields):

```json
{
  "id": "DEPLOY001",
  "category": "deployment",
  "severity": "critical",
  "evidence": "Matched risk vocabulary: Deploy",
  "certainty": "signal",
  "requires_approval": true
}
```

Full generated outputs: [JSON](examples/scan.json), [Markdown](examples/report.md), [HTML](examples/report.html), [dependency graph](examples/graph.json), [synthetic backtest](examples/backtest.synthetic.json). Git-dependent readiness can change with workspace state. It is a bounded penalty score, never a percentage chance of success.

## Plans and checks

Prefer explicit JSON dependencies; `.txt` plans are imported as sequential steps. Input contract and all fields: [reference](references/input-contract.md). A minimal plan:

```json
{
  "goal": "Review project",
  "acceptance": ["Review is recorded"],
  "steps": [{"id": "inspect", "description": "Inspect configuration", "tools": ["git"], "paths": ["pyproject.toml"]}]
}
```

Findings distinguish `confirmed` local issues, textual `signal`s and `speculative` missing context. Each includes ID, category, severity, evidence, impact, suggested checks, repairs and approval requirement. Rules cover environment, files, data, permissions, network, deployment, task definition and agent behavior. See [complete rule catalog](docs/rules.md).

Static simulation checks declared executable presence, local paths, environment variable presence, installed Python package versions, top-level config parsing, acceptance criteria, dependency cycles, missing producers and rollback declarations. It never executes task commands or validates live remote credentials. Rollback/backup declarations are not restoration tests.

## Historical forecasts

Supply pre-execution plans with `plan_recorded_at` and `outcome_recorded_at` timestamps. The deterministic logistic model uses chronological training/calibration/selection/test isolation (50/20/15/15), sigmoid calibration and a training-prevalence baseline. The selection block gates probability output; the final test only reports quality. Missing provenance, fewer than 120 records, inadequate fitting/selection class support, overlapping availability times, known group overlap or selection performance no better than baseline cause fallback. `--as-of` excludes results not yet recorded, including delayed outcomes. [Model assumptions, validation and limits](docs/model.md).

Synthetic example data is deliberately easy and is not a performance benchmark. No accuracy or calibration guarantee is claimed for real tasks. The tool does not train on user repositories automatically or transmit training records.

## Agent Skill

Keep the full repository folder as the skill bundle, with [SKILL.md](SKILL.md) at its root, and separately install the Python package in the agent's trusted runtime. [Client-specific installation and policy exits](docs/agent-integration.md) documents Codex, Claude Code and Cursor locations from official sources. Actual automatic invocation remains unverified; CLI integration is tested.

## Safety and development

[Security boundaries](SECURITY.md): no planned command execution, no script imports, no recursive source scraping, bounded files, traversal/link rejection, sanitized reports and inert HTML. Trusted installed Python/Git and a stable filesystem snapshot are assumed. Redaction is best effort; inspect reports before sharing.

```sh
python -m pip install -e ".[test]"
python -m unittest discover -s tests -v
python -m pip install build "setuptools>=77" wheel
python -m build
python scripts/verify_distribution.py
```

See [contribution guide](CONTRIBUTING.md), [release procedure](docs/release.md) and [actual local validation](docs/validation.md). GitHub Actions config targets Linux/macOS/Windows and Python 3.10–3.13; local Windows Python 3.12 results do not verify the other matrix entries. MIT licensed.
