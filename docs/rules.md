# v0.1.0 rule catalog

All findings include impact, checks and proposed repairs. Severity is a review priority, not a probability. Text rules are case-insensitive vocabulary matches and may over/under-detect negations, obfuscations and languages. Structured checks only inspect declared prerequisites.

| ID | Category | Trigger | Certainty | Approval |
| --- | --- | --- | --- | --- |
| FILE001 | file | Delete/remove/overwrite/truncate vocabulary | signal | yes |
| DATA001 | data | Migration/drop table/truncate table vocabulary | signal | yes |
| PERM001 | permission | Elevated privilege or credential vocabulary | signal | yes |
| NET001 | network | URL/download/fetch/curl/remote API vocabulary | signal | no |
| DEPLOY001 | deployment | Production/deploy/apply vocabulary | signal | yes |
| AGENT001 | agent | Prompt override/exfiltration vocabulary | signal | yes |
| AGENT002 | agent | Unbounded retry or indefinite execution vocabulary | signal | no |
| ENV001 | environment | Dependency installation/version conflict vocabulary | signal | no |
| TASK001 | task | Missing goal or steps | speculative | no |
| TASK002 | task | Missing acceptance criteria | speculative | no |
| GIT001 | file | Uncommitted workspace changes | confirmed | no |
| GIT002 | file | Git cleanliness cannot be established | signal | no |
| CONFIG001 | environment | Invalid, linked, oversized or unreadable top-level config | confirmed | no |
| CONFIG002 | environment | TOML parser unavailable on Python 3.10 | signal | no |
| TOOL001 | environment | Declared tool missing from PATH or invalid name | confirmed | no |
| PATH001 | file | Traversal, absolute or linked project path | confirmed | yes |
| PATH002 | file | Required path missing or unreadable | confirmed | no |
| ENV002 | permission | Required environment variable missing/empty | confirmed | no |
| ENV003 | environment | Unsupported package constraint syntax | confirmed | no |
| ENV004 | environment | Package missing, incompatible or unverifiable numeric version | confirmed | no |
| SAFE001 | data | Dangerous step lacks reversibility/rollback declaration | signal | yes |
| SAFE002 | data | Database change lacks backup declaration | signal | yes |
| NET002 | network | Network step lacks timeout/bounded retry declarations | signal | no |
| PLAN001 | task | Dependency references nonexistent step | confirmed | no |
| PLAN002 | task | Listed step precedes its dependency | confirmed | no |
| PLAN003 | task | Dependency cycle | confirmed | no |
| PLAN004 | task | Required artifact lacks ancestor producer or declared input | confirmed | no |

Readiness starts at 100 and subtracts low=3, medium=8, high=15, critical=25 per distinct rule, with a floor of zero. Repeated findings retain `occurrences` but do not multiply penalties. A high readiness score cannot prove safety; absent declarations may hide real risks. Dependency graph findings preserve individual graph violations, while the top-level scan findings are consolidated by ID.
