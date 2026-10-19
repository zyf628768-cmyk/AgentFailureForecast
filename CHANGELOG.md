# Changelog

## 0.1.0 — 2026-10-19

Initial MVP: eight-category deterministic rules, explicit dependency graph validation, bounded offline static rehearsal, optional chronological logistic forecasting with sigmoid calibration and baseline gating, six CLI commands, JSON/Markdown/HTML reporting and Agent Skills entrypoint. Historical quality has only been exercised with synthetic fixtures; real-world probability validity is unverified.

Pre-release review fixes (same unpublished version): atomic report replacement prevents hard-link target corruption; Git filter/submodule/diff configuration is rejected before inspection; Git executable lookup excludes relative/CWD locations; auth headers and prefixed secrets are redacted; ambiguous/nonfinite JSON input is rejected. Historical model v2 adds an independent selection block, availability-time provenance and known-group isolation. Source distributions now include test evidence, and CI verifies sdist-to-wheel round trips and fresh offline installations.

Release-readiness improvements: optional severity-policy exit code 3, bounded declaration counts, rejection of overflowing JSON numbers, Windows reparse protection on older supported Python versions, official client installation references and a manual GitHub release workflow gated by the complete cross-platform matrix.
