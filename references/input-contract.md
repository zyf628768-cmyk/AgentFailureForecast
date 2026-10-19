# Input contract

All JSON is UTF-8, capped at 2 MB per file. Duplicate keys and all nonfinite numbers (including overflowing exponents) are rejected. Plan schema: `schemas/plan.schema.json`. Up to 500 steps and 10000 combined prerequisite/dependency declarations across `inputs`, `depends_on`, `tools`, `paths`, `env`, `packages`, `requires` and `produces`. Required step `id` values are unique nonempty strings. Fields:

* `goal`: intended outcome; `acceptance`: observable success criteria; `inputs`: already available artifact names.
* `steps`: each contains `id`, `description`, optional `depends_on` step IDs.
* `tools`: executable names queried in PATH, never executed. This proves presence, not operational capability.
* `paths`: required existing relative workspace paths. Traversal, absolute and symlink/junction paths rejected. Generated future files should use `produces`, not `paths`.
* `env`: required variable names; only presence checked, values never reported. Credential validity and remote permissions remain unverified.
* `packages`: installed Python distribution names, optionally one numeric `==`, `>=`, `<=`, `<` or `>` constraint. Complex PEP 440 ranges and prereleases are deliberately unverified and raise a finding.
* `requires`, `produces`: logical artifacts. Required artifacts need a transitive dependency producer or a declared input.
* `reversible`, `rollback`, `backup`, `timeout`, `retries`: boolean declarations; `retries=true` means a bounded retry policy exists. They do not prove implementation or backup health.

Plain `.txt` input imports nonempty lines as sequential steps and leaves acceptance absent. No inference of arbitrary natural-language dependencies is claimed. No scan recursively reads source trees. Configuration checks cover top-level `pyproject.toml`, `package.json`, and bounded reading of `requirements.txt`; requirements content is not executed or automatically installed.

History is a JSON array of unique `task_id` records with ISO timezone-aware `started_at`, `finished_at`, boolean `failed`, a pre-execution `plan`, optional `tools_used` array and `failure_type` string. Probability mode additionally requires timezone-aware `plan_recorded_at <= started_at` and `outcome_recorded_at >= finished_at`. Missing provenance causes rules fallback; inconsistent timestamps are rejected. Only outcomes recorded strictly before `--as-of` are available for fitting. Optional nonempty `group_id` must be present on all records if used and may not repeat across time blocks. `tools_used` and failure metadata are accepted for auditing but excluded from features. The schema allows legacy records without provenance for safe ingestion; they cannot yield statistical forecasts. Duplicate JSON keys and nonfinite JSON constants are rejected.
