# Installing the Skill bundle

Install the Python wheel into a trusted virtual environment first. Keep its `forecast` executable on the agent's PATH (or supply its absolute path). Installing the wheel installs the engine; install the **full source folder** separately as the Skill bundle so `SKILL.md`, `references/` and `docs/` stay together.

Use one project-scoped location appropriate to your client:

| Client | Bundle destination inside the target repository |
| --- | --- |
| Codex | `.agents/skills/agent-failure-forecast/` |
| Claude Code | `.claude/skills/agent-failure-forecast/` |
| Cursor | `.cursor/skills/agent-failure-forecast/` (also supports `.agents/skills/`) |

For example, copy the extracted `agent-failure-forecast` folder into `.agents/skills/`. Its entrypoint must then be `.agents/skills/agent-failure-forecast/SKILL.md`. Keep the Python runtime outside an untrusted target repository. Prefer the installed executable rather than `python -m` from an untrusted directory, which could shadow imports.

Ask the client to use `agent-failure-forecast` to analyze a concrete task. Confirm it invokes `forecast scan` or `simulate`, interprets certainty and approval flags and does not execute the proposed operations. Skill discovery and model tool selection depend on the actual client/version and are not proven by CLI tests. No live client auto-invocation was verified locally.

For automated orchestration:

```sh
forecast scan --root target-project --plan plan.json --fail-on high --output preflight.json
```

The report is written before the policy decision. Exit **0** means analysis completed below the selected threshold (or no threshold was selected); **2** means an input/output error; **3** means a finding meets/exceeds `--fail-on`. The option is supported by scan, plan, simulate and predict. Exit 0 never proves the proposed operation is safe. Approval flags still require the agent to check existing authorization.

These project locations were checked against official documentation on 2026-10-19: [OpenAI local Skill discovery](https://learn.chatgpt.com/docs/build-skills#where-codex-loads-local-skills), [Claude Code Skills](https://code.claude.com/docs/en/skills), [Cursor Skill directories](https://cursor.com/docs/skills#skill-directories). Hosted/remote clients may have different discovery and synchronization rules.
