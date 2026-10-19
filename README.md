# AgentFailureForecast

## 让 Agent 动手之前，先看清可能失败在哪里

**给 AI Agent 一份执行前的风险检查单：发现隐患，说明证据，提出可验证的预防措施。**

一次数据库迁移没有备份，一次部署没有回滚，一个步骤依赖尚未生成的文件——这些问题，值得在执行前被看见。AgentFailureForecast 将任务计划与本地环境一起检查，帮助你决定：哪些可以继续，哪些需要补齐条件，哪些必须先获得人工批准。

**离线扫描 · 默认只读 · 8 类风险 / 27 条规则 · 无第三方运行时依赖 · 无需付费模型密钥**

| 执行前的问题 | 工具给出的检查结果 |
| --- | --- |
| 文件会被覆盖，工作区还有未提交修改？ | 文件操作风险信号、Git 工作区状态和检查建议 |
| 数据库变更没声明备份，生产部署缺少回滚？ | 高优先级风险、人工批准标记和预防措施 |
| 工具、路径、环境变量或依赖包没准备好？ | 对声明的前置条件进行本地检查，给出缺失证据 |
| 多步骤计划存在循环依赖或顺序错误？ | 可导出的 JSON 依赖图和具体依赖问题 |
| Agent 读取了可疑指令，或计划无限重试？ | 指令注入、无界重试等词汇信号及审查建议 |

适合在让 Agent **批量改文件、调整依赖、准备迁移或部署、执行多步骤任务**之前运行。支持独立 CLI，也提供供 Codex、Claude Code 等客户端集成的标准 [SKILL.md](SKILL.md)；客户端自动触发仍待实测。

```sh
# 在本项目目录安装后，用随附计划体验一次执行前检查
forecast scan --root . --plan examples/plan.json
# 在自动化流程中，发现 high 及以上风险时返回退出码 3
forecast simulate --root . --plan examples/plan.json --fail-on high
```

随附计划会触发生产部署、数据库变更、缺少回滚/备份声明等风险；检查过程不会执行这些操作。查看 [实际报告](examples/report.md)、[完整中文指南](README.zh-CN.md) 或 [下载 v0.1.0 预发布版](https://github.com/zyf628768-cmyk/AgentFailureForecast/releases/tag/v0.1.0)。

**可核验的交付：** v0.1.0 在 Windows、Linux、macOS × Python 3.10–3.13 的 12 组 CI 中，每组 120 项测试全部通过，并完成独立安装与 CLI 验证。[查看发布验证记录](https://github.com/zyf628768-cmyk/AgentFailureForecast/actions/runs/39241024824)。这些结果证明已测试行为与安装流程，不代表真实任务的预测准确率。

当前为 v0.1.0 MVP。规则输出风险和准备度；可选历史模型在数据与验证条件满足时才输出概率，真实生产预测效果尚未验证。

---

## English overview

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

See [contribution guide](CONTRIBUTING.md), [release procedure](docs/release.md) and [validation details](docs/validation.md). The [v0.1.0 release workflow](https://github.com/zyf628768-cmyk/AgentFailureForecast/actions/runs/39241024824) passed all 12 Linux/macOS/Windows × Python 3.10–3.13 configurations, with 120 tests and distribution verification in each. MIT licensed.
