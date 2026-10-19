# AgentFailureForecast v0.1.0

Predict Agent Failures Before They Happen.

Initial local MVP release: zero-dependency Python engine, six installed CLI commands, standard SKILL.md, eight-category deterministic risk rules, JSON dependency graph with cycle/missing-prerequisite checks, read-only offline static rehearsal and escaped JSON/Markdown/HTML reports.

Pre-release security review fixes hard-link output corruption, repository filter execution and incomplete sensitive-value redaction. Git lookup excludes relative/CWD executables and JSON rejects duplicate keys and nonfinite constants. Historical model v2 separates training/calibration/selection/final-test blocks, requires pre-execution snapshot and outcome-availability timestamps, filters delayed results and isolates known groups. Final-test labels affect reporting only. The 240-record fixture is synthetic and demonstrates mechanics only; real-world prediction quality is unverified.

Local validation: 120 automated tests passed; 16 report-generation and 18 distribution-verification CLI invocations passed; standard Skill and JSON Schema validation passed. The sdist rebuild reproduces engine Python bytes and installs offline in a fresh venv. Optional `--fail-on` enables severity-based policy exits, bounded declarations prevent oversized dependency workloads, and older supported Windows Python versions reject reparse points. Official client installation references and a manually dispatched, cross-platform-CI-gated release workflow are included. Only Windows/Python 3.12 has been run locally. Remote results are established separately by actual workflow execution; agent-client autodiscovery remains unverified. The version remains 0.1.0 because no public release was published; original local snapshots are retained under before-review/readiness tags.

Assets: universal Python wheel, source distribution, full project source zip and SHA-256 checksums. See README/README.zh-CN for installation and usage, SECURITY.md for boundaries and docs/validation.md for actual evidence. This release preparation does not publish to GitHub or PyPI.
