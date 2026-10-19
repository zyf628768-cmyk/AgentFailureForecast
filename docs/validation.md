# Actual local validation — v0.1.0

Validation date: 2026-10-19 (Asia/Shanghai). Environment: Windows x64, CPython 3.12.14, Git 2.53.0.windows.1.

## Automated tests

`python -m unittest discover -s tests -v`: **118 run, 118 passed, 0 failures, 0 errors, 0 skipped**. Full output: [test-results.txt](test-results.txt). Windows link tests were executed in an OS context permitting actual hard-link/symlink creation; no mocked link test or skip was counted as a pass.

Coverage includes all eight risk categories, irreversible operations, Git clean/dirty and environment isolation, scoped Git trust, unsafe Git includes/worktree metadata/symlinks, prerequisite paths, missing tools/packages/environment variables, config errors, dependency graph validity/missing prerequisites/order/cycles/500-step limit, sensitive report filtering, inert Markdown/HTML, default offline behavior, no command execution, insufficient history, chronological splits, future outcome exclusion, calibration, baseline gating, test-label isolation, expanding backtests, Draft 2020-12 JSON Schema validation and all six CLI commands.

The initial MVP suite had 84 passing tests. Pre-release review added 24 regression cases, and release readiness added ten more covering numeric overflow, declaration limits, legacy Windows reparse detection, policy exits and Unicode output. Real reproductions exposed hard-link target corruption, repository clean-filter execution, test-set model selection, delayed-result leakage, unverified plan provenance, missing group isolation and redaction/input ambiguities. These were fixed and the complete 118-case run passed. Old assertions about three-way splitting were updated to the corrected four-way contract; no failing case was removed or disabled. See [review findings](review-v0.1.0.md).

## Packaging and end-to-end acceptance

* `python -m build --no-isolation`: wheel and sdist successfully generated using installed build backends.
* Fresh venv created without pip. The test environment's pip installed the wheel into it with `--no-index`; no runtime dependencies were downloaded or required.
* Installed `forecast` ran from outside the source directory, with PYTHONPATH removed. Imported module location was confirmed inside the new venv's site-packages.
* **16 installed CLI invocations all exited 0**: scan, plan, simulate, prediction without history, prediction with synthetic history, backtest, Markdown/HTML report conversion, global help, six subcommand helps and version. Exact portable command forms: [acceptance.json](acceptance.json).
* Six generated example documents validated with the official `jsonschema` Draft 2020-12 validator: four reports, input plan and history. Graph output is additionally schema-covered by automated tests.
* `python scripts/verify_distribution.py`: source manifest complete (including test evidence); sdist rebuilt to a wheel with byte-identical engine Python files; separate fresh venv installed the wheel offline and ran **18 CLI invocations**, including all six commands, all three report formats, policy exit 3, help and version. Evidence: [distribution-verification.json](distribution-verification.json). The same script is configured in every CI matrix job.
* Bundled skill-creator `quick_validate.py`: **Skill is valid!**
* Example outputs are generated from the checked-in plan and deterministic 240-record synthetic fixture. The fixture can be regenerated with `python scripts/generate_examples.py`.

The 16 report-generation acceptance calls and 18 distribution verification calls are additional to the 118 unittest cases, not extra unit tests. Test dependencies used locally: jsonschema 4.26.0; build 1.6.1; setuptools 84.0.0; wheel 0.48.0. The Skill/workflow YAML validation additionally used PyYAML 6.0.3. The engine itself has no third-party runtime dependencies. Distribution verification uses installed build dependencies and does not access a package index.

## Model capabilities actually checked

Synthetic tests verify deterministic fitting, a separately fitted sigmoid calibrator, chronological training/calibration/selection/test blocks, selection-gated baseline comparison and untouched-test metrics. Changing final-test labels cannot alter eligibility, model version or weights, even with a single test class. Tests also cover delayed outcome availability, post-execution plan timestamps, absent provenance fallback, group leakage, temporal overlap, reliability bins and insufficient-data/class-support fallback. Timestamps and groups are declarations; data authenticity remains unverified. There are no real task records, external holdout results or verified prospective failure rates. Synthetic report scores must not be presented as real-world accuracy.

## Unverified and constrained

* Linux/macOS and Python 3.10/3.11/3.13 have not been executed here. The GitHub Actions matrix is prepared, not remotely run.
* Automatic Skill discovery/invocation in Codex, Claude Code and Cursor has not been tested. The standard entrypoint and installed CLI are verified locally.
* Official Skill discovery directories have been checked and documented. The release workflow YAML and its gating/permission structure parse successfully locally; actual remote workflow execution still requires the target repository. WSL was present only as an installer stub, and no Docker runtime was available, so no local Linux result is claimed.
* Git worktrees/submodules, active filter/diff/submodule config, linked metadata and local config includes are deliberately reported as unverified. Metadata over 10000 entries is not inspected.
* Natural-language dependency inference, remote credential validity, real backup restoration and live deployment behavior are outside static simulation.
* PATH tools and system Python/Git must be trusted; concurrent malicious filesystem mutations are outside the boundary guarantee. Redaction is best effort.
* These are local validation results. Remote publication and matrix results must be established separately from actual GitHub workflow runs in the linked repository; the release workflow blocks publication until those jobs pass. No PyPI publication is performed by this project.

For the prepared local commit/tag and final clean status, inspect the delivered repository. Source zip, sdist, wheel and SHA256SUMS are supplied in the sibling release directory.
