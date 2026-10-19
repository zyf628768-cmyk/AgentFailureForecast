# Contributing

Use Python 3.10 or later. In a virtual environment run `python -m pip install -e ".[test]"` then `python -m unittest discover -s tests -v`. Runtime has no third-party dependencies. The test extra supplies the official JSON Schema validator.

For fixes, add a reproducible test of observable behavior, run the suite and CLI examples, and document limitations. Do not add network access, command execution or data collection to scanning. Rule changes need documented IDs and uncertainty levels. Historical features must be available before execution; fitting, calibration and evaluation must stay disjoint in time.

CI covers Windows, Ubuntu and macOS on Python 3.10–3.13. A configured matrix is not evidence that platforms have passed until its jobs actually run. Never publish synthetic benchmark metrics as real-world accuracy. Use fictional fixtures without secrets. For release build `python -m build`, run `python scripts/verify_distribution.py` (requires pip 22.3+ and installed build backends), and follow `docs/release.md`. Windows hard-link/symlink regression cases require an OS context that permits creating those links; do not hide failures by removing tests.
