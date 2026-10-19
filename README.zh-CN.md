# AgentFailureForecast

**在 Agent 执行前识别潜在失败点。**

这是可安装、可运行的 Python CLI 与标准 Agent Skill，不依赖付费模型密钥。默认离线、只读，不执行待检查任务中的命令。v0.1.0 使用透明规则；可选历史模型仅用合成数据验证机制，尚无真实生产预测效果证据。

## 安装与运行

需要 Python 3.10+，Git 用于检查工作区。进入本项目目录：

```sh
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# Linux/macOS: source .venv/bin/activate
python -m pip install .
forecast --help
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

也可安装 Release wheel；使用 `pip install --no-index wheel文件路径` 可完全离线安装。源码构建依赖首次可能需要下载；扫描不联网。可用 `python -m agent_failure_forecast` 替代 `forecast`。

命令默认输出至标准输出，仅指定 `--output` 才写报告；已有文件需要 `--force` 原子替换。默认退出码 0 表示分析完成，**不表示任务安全**；退出码 2 表示输入输出错误。scan/plan/simulate/predict 可添加 `--fail-on high`，先写报告，达到风险阈值后返回退出码 3。上层 Agent 仍须查看批准字段。

## 输入与输出

推荐使用显式 JSON：`goal`、`acceptance`、`steps`，每步提供唯一 `id`、`description`、`depends_on`。工具、路径、环境变量名、Python 包版本、产物和前置产物可声明为数组。`.txt` 仅按行顺序转换，不声称能理解任意自然语言中的隐藏依赖。

每项风险包含 ID、类别、级别、证据、影响、检查建议、修复建议和批准标记；`confirmed` 表示本地检查确认，`signal` 表示风险信号，`speculative` 表示信息不足引起的推测。准备度是规则扣分结果，不是成功率或失败率。

示例计划实际触发 `DEPLOY001`（生产部署风险，critical，signal，需要批准），以及数据库变更、缺少回滚、缺少备份、网络超时/重试策略等风险。完整输出见 [JSON](examples/scan.json)、[Markdown](examples/report.md)、[HTML](examples/report.html) 和 [依赖图](examples/graph.json)。规则清单见 [docs/rules.md](docs/rules.md)。

静态预演检查工具是否存在、必要路径、Git 状态、顶层配置、已安装 Python 包元数据、环境变量是否存在、验收条件和可逆性声明。不会运行工具来测试其功能，不验证远端凭证，不执行真实部署、删除、迁移或付费调用。声明有备份不等于恢复测试通过。

## 历史模型

历史记录包含唯一任务 ID、开始/完成时间、计划快照记录时间 `plan_recorded_at`、结果可用时间 `outcome_recorded_at`、执行前计划及失败标签。仅执行前特征进入模型。按时间排序后 50% 训练、20% 概率校准、15% 选择、15% 最终测试；选择集决定是否允许概率输出，最终测试集只报告质量，不参与准入和拟合。

少于 120 条、缺少快照/结果可用时间、训练/校准/选择集正负样本不足、时间泄漏或选择集未优于基准时，停止输出概率并降级到规则模式。`--as-of` 按结果实际记录时间过滤延迟反馈；可选 `group_id` 用于排除已知事件组跨分区重复，使用时必须完整标注。旧历史文件可读取，但缺少时间来源信息时不输出概率。输出模型版本、数据版本、样本量、Brier 分数和校准分箱等。`backtest` 使用扩展时间窗口，各轮并非独立试验。详见 [模型说明](docs/model.md)。合成示例不能用于宣传真实准确率。

## Skill 与安全

将整个项目目录保留为 Skill 包，根目录包含 [SKILL.md](SKILL.md)，同时在 Agent 的可信 Python 环境安装引擎。具体 Codex、Claude Code、Cursor 的发现目录和安装方法见 [客户端集成说明](docs/agent-integration.md)，已核对官方文档。本次未实测客户端自动触发，CLI 集成已验证；在不可信目录中优先使用已安装的 `forecast` 可执行程序，避免本地模块遮蔽。

默认不读取全部源码、不上传数据、不执行项目脚本；项目相对路径拒绝越界及符号链接/目录联接；报告不回显计划正文、Git 文件名或环境变量值。HTML 转义，敏感信息过滤为尽力而为。并发恶意文件系统修改、被篡改的系统 Git/Python 不在安全保证内，发布报告前应人工检查。详见 [SECURITY.md](SECURITY.md)。

```sh
python -m pip install -e ".[test]"
python -m unittest discover -s tests -v
python -m pip install build "setuptools>=77" wheel
python -m build
python scripts/verify_distribution.py
```

实际验证见 [docs/validation.md](docs/validation.md)，发布方法见 [docs/release.md](docs/release.md)。本地仅验证 Windows/Python 3.12；Linux/macOS 和其他 Python 版本配置了 CI，尚未执行，不能视为通过。许可证 MIT。
