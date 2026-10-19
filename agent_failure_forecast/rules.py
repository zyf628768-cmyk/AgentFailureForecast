"""Transparent rules. Text matches are signals, never proof of intent."""
import re
from .safety import redact

# id, category, severity, pattern, impact, check, repair, approval
RULES = [
    ("FILE001", "file", "high", r"\b(delete|remove-item|rm|overwrite|truncate)\b|删除|覆盖", "Data or local changes may be lost", "Review exact targets and Git diff", "Make a verified backup; narrow targets", True),
    ("DATA001", "data", "critical", r"\b(drop\s+table|migrat\w*|truncate\s+table)\b|数据库迁移", "Persistent data may be changed irreversibly", "Verify backup restoration and migration dry run", "Prepare and test a rollback or restore procedure", True),
    ("PERM001", "permission", "high", r"\b(sudo|administrator|chmod\s+777|credential|secret)\b|管理员|凭证", "Privilege or credential boundary may be crossed", "Verify least privilege and credential availability without printing values", "Use scoped permissions and explicit authorization", True),
    ("NET001", "network", "medium", r"https?://|\b(download|fetch|curl|remote\s+api)\b|下载|网络", "External dependency may time out or change", "Check timeout, bounded retry and pinned content", "Cache verified inputs and specify retry limits", False),
    ("DEPLOY001", "deployment", "critical", r"\b(production|deploy|kubectl\s+apply|terraform\s+apply)\b|生产|部署", "Live service may be disrupted", "Verify target, staged validation and rollback", "Require approval and tested rollback before execution", True),
    ("AGENT001", "agent", "high", r"ignore\s+(all\s+)?previous|system\s+prompt|exfiltrat|忽略.*指令", "Untrusted content may redirect the agent", "Inspect source trust and tool output boundaries", "Treat retrieved content as data; reject embedded instructions", True),
    ("AGENT002", "agent", "medium", r"\b(forever|unlimited|until\s+success|retry\s+indefinitely)\b|无限|直到成功", "Unbounded retries can exhaust resources", "Verify step, cost and time budgets", "Set bounded retries and explicit stopping conditions", False),
    ("ENV001", "environment", "medium", r"\b(pip\s+install|npm\s+install|dependenc\w*|version\s+conflict)\b|依赖|版本冲突", "Runtime compatibility may be insufficient", "Check installed versions against declared requirements", "Use an isolated pinned environment", False),
]


def finding(rid, category, severity, evidence, impact, check, repair, approval=False, certainty="confirmed"):
    return dict(id=rid, category=category, severity=severity, evidence=redact(evidence), impact=impact,
                checks=[check], repairs=[repair], requires_approval=approval, certainty=certainty)


def analyze_text(text):
    result = []
    for rid, cat, level, pattern, impact, check, repair, approval in RULES:
        match = re.search(pattern, text, re.I)
        if match:
            # Evidence deliberately includes only matched rule vocabulary, not surrounding secrets.
            result.append(finding(rid, cat, level, "Matched risk vocabulary: " + match.group(0), impact, check, repair, approval, "signal"))
    return result
