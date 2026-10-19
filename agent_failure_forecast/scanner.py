"""Read-only probes: no shell, no imports from inspected projects, no network."""
import importlib.metadata
import os
from pathlib import Path
import re
import shutil
import subprocess
from .planner import normalize, build_graph
from .rules import analyze_text, finding
from .safety import safe_path, read_text, parse_json


def trusted_git(root):
    """Resolve only absolute PATH entries, never implicit Windows CWD lookup."""
    root = Path(root).resolve()
    cwd = Path.cwd().resolve()
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        directory = Path(entry.strip('"'))
        if not directory.is_absolute():
            continue
        try:
            directory = directory.resolve()
            if directory == cwd or directory.is_relative_to(root):
                continue
            candidate = directory / ("git.exe" if os.name == "nt" else "git")
            resolved = candidate.resolve()
            if candidate.is_file() and os.access(candidate, os.X_OK) and not resolved.is_relative_to(root):
                return str(resolved)
        except (OSError, RuntimeError):
            continue
    return None


def git_state(root):
    root = Path(root).resolve()
    executable = trusted_git(root)
    if not executable:
        return {"status": "unavailable"}
    if Path(executable).resolve().is_relative_to(Path(root).resolve()):
        return {"status": "untrusted_git_executable"}
    try:
        metadata = safe_path(root, ".git")
        if not metadata.exists():
            return {"status": "not_repository_or_unreadable"}
        if not metadata.is_dir():
            return {"status": "external_git_metadata_rejected"}
        count = 0
        def walk_error(error):
            raise error
        for directory, dirs, files in os.walk(metadata, followlinks=False, onerror=walk_error):
            for name in dirs + files:
                count += 1
                safe_path(root, (Path(directory)/name).relative_to(root))
                if count > 10000:
                    return {"status": "git_metadata_limit_exceeded"}
        for config in (metadata / "config", metadata / "config.worktree"):
            if config.exists():
                content = read_text(config)
                if re.search(r"(?im)^\s*\[\s*include|^\s*worktree\s*=", content):
                    return {"status": "external_git_config_rejected"}
                if re.search(r"(?im)^\s*\[\s*(?:filter|submodule|diff)\b", content):
                    return {"status": "active_git_config_rejected"}
        if (root/".gitmodules").exists():
            return {"status": "submodule_inspection_unsupported"}
        if (metadata/"commondir").exists() or (metadata/"objects"/"info"/"alternates").exists():
            return {"status": "external_git_metadata_rejected"}
    except (ValueError, OSError, UnicodeError):
        return {"status": "unsafe_or_unreadable_git_metadata"}
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
    env.update(GIT_OPTIONAL_LOCKS="0", GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
    try:
        result = subprocess.run([executable, "--no-optional-locks", "-c", "safe.directory=" + str(Path(root).resolve()), "-c", "core.fsmonitor=false", "-c", "core.hooksPath=" + os.devnull,
                                 "-c", "core.attributesFile="+os.devnull, "-c", "core.excludesFile="+os.devnull,
                                 "-c", "status.submoduleSummary=false", "-C", str(root), "status", "--porcelain", "--untracked-files=normal", "--ignore-submodules=all"],
                                shell=False, capture_output=True, timeout=10, env=env)
        if result.returncode:
            return {"status": "not_repository_or_unreadable"}
        return {"status": "dirty" if result.stdout.strip() else "clean"}
    except (OSError, subprocess.TimeoutExpired):
        return {"status": "unavailable"}


def scan(root, plan):
    try:
        root = Path(root).resolve(strict=True)
    except RuntimeError:
        raise ValueError("root contains a link cycle") from None
    if not root.is_dir():
        raise ValueError("root must be a directory")
    plan = normalize(plan)
    graph = build_graph(plan)
    text = plan.get("goal", "") + "\n" + "\n".join(s.get("description", "") for s in plan.get("steps", []))
    findings = analyze_text(text) + graph["findings"]
    checks = []
    def add(rid, category, evidence, check, repair, severity="high", approval=False, certainty="confirmed"):
        findings.append(finding(rid, category, severity, evidence, "Task may fail or exceed its intended boundary", check, repair, approval, certainty))
    if not plan.get("goal", "").strip() or not plan.get("steps"):
        add("TASK001", "task", "Goal or executable steps missing", "Clarify intended outcome", "Provide a goal and concrete steps", "medium", certainty="speculative")
    if not plan.get("acceptance"):
        add("TASK002", "task", "Acceptance criteria absent", "Define observable success", "Add verifiable acceptance criteria", "medium", certainty="speculative")
    state = git_state(root)
    checks.append({"kind": "git", **state})
    if state["status"] == "dirty":
        add("GIT001", "file", "Git workspace has uncommitted changes", "Inspect local diff before writes", "Preserve or commit existing work", "high")
    elif state["status"] != "clean":
        add("GIT002", "file", "Git cleanliness could not be established", "Check repository availability", "Establish an independent backup", "low", certainty="signal")
    for config in ("pyproject.toml", "package.json", "requirements.txt"):
        try:
            path = safe_path(root, config)
            if path.exists():
                content = read_text(path)
                valid = True
                if config.endswith(".json"):
                    valid = isinstance(parse_json(content), dict)
                elif config.endswith(".toml"):
                    try:
                        import tomllib
                    except ImportError:
                        valid = None
                    else:
                        tomllib.loads(content)
                checks.append({"kind": "config", "name": config, "valid": valid})
                if valid is None:
                    add("CONFIG002", "environment", "TOML validation requires Python 3.11+", "Validate configuration on Python 3.11+", "Use a supported TOML parser", "low", certainty="signal")
                elif not valid:
                    raise ValueError("invalid configuration")
        except (OSError, ValueError, UnicodeError):
            add("CONFIG001", "environment", "Project configuration is invalid, linked or unreadable", "Inspect project config manually", "Correct configuration or use an ordinary local file")
    for step in plan.get("steps", []):
        for tool in step.get("tools", []):
            # A tool name is only queried, never launched.
            valid = bool(re.fullmatch(r"[A-Za-z0-9_.+-]+", tool)) and bool(shutil.which(tool, path=os.environ.get("PATH", "")))
            checks.append({"kind": "tool", "available": valid})
            if not valid:
                add("TOOL001", "environment", "A declared tool is unavailable or has an invalid name", "Check tool installation and PATH", "Install the declared tool through a trusted channel")
        for name in step.get("paths", []):
            try:
                target = safe_path(root, name)
                if not target.exists():
                    raise FileNotFoundError()
                if not os.access(target, os.R_OK):
                    raise PermissionError()
                checks.append({"kind": "path", "available": True})
            except ValueError:
                add("PATH001", "file", "Traversal, absolute path or linked path rejected", "Verify the workspace boundary", "Use a relative ordinary path inside root", approval=True)
            except OSError:
                add("PATH002", "file", "Required path is missing or unreadable", "Check prerequisites and file permissions", "Provide the required local artifact")
        for name in step.get("env", []):
            if not os.environ.get(name):
                add("ENV002", "permission", "A required environment variable is missing or empty", "Check variable presence without printing its value", "Configure the required scoped credential or setting")
        for requirement in step.get("packages", []):
            match = re.fullmatch(r"([A-Za-z0-9_.-]+)(?:(==|>=|<=|>|<)([0-9]+(?:\.[0-9]+)*))?", requirement)
            if not match:
                add("ENV003", "environment", "Unsupported package constraint", "Use name or a single numeric version comparison", "Simplify constraint; verify complex specifiers separately")
                continue
            name, op, version = match.groups()
            try:
                installed = importlib.metadata.version(name)
                if op:
                    if not re.fullmatch(r"\d+(?:\.\d+)*", installed):
                        raise ValueError()
                    a, b = tuple(map(int, installed.split("."))), tuple(map(int, version.split(".")))
                    n = max(len(a), len(b))
                    a, b = a + (0,) * (n-len(a)), b + (0,) * (n-len(b))
                    if not {"==": a == b, ">=": a >= b, "<=": a <= b, ">": a > b, "<": a < b}[op]:
                        raise ValueError()
            except (importlib.metadata.PackageNotFoundError, ValueError):
                add("ENV004", "environment", "A declared package is missing or its version is incompatible/unverifiable", "Compare installed metadata with the declared requirement", "Install a compatible version in an isolated environment")
        desc = step.get("description", "")
        step_risks = analyze_text(desc)
        destructive = any(r["id"] in ("FILE001", "DATA001", "DEPLOY001") for r in step_risks)
        if destructive and (step.get("reversible") is not True or not step.get("rollback")):
            add("SAFE001", "data", "Dangerous step lacks declared reversibility and rollback", "Verify restoration independently", "Prepare a verified rollback before approval", "critical", True, "signal")
        if any(r["id"] == "DATA001" for r in step_risks) and not step.get("backup"):
            add("SAFE002", "data", "Data mutation lacks a declared backup", "Test backup restoration", "Create and verify backup before execution", "critical", True, "signal")
        if any(r["id"] == "NET001" for r in step_risks) and not (step.get("timeout") and step.get("retries")):
            add("NET002", "network", "Network step lacks declared timeout or bounded retries", "Inspect request policy", "Declare and enforce timeout and retry bounds", "medium", certainty="signal")
    # Findings are per rule, with count retained; no raw task text is echoed.
    unique = {}
    for f in findings:
        if f["id"] not in unique:
            unique[f["id"]] = dict(f, occurrences=1)
        else:
            unique[f["id"]]["occurrences"] += 1
    findings = list(unique.values())
    penalty = sum({"low": 3, "medium": 8, "high": 15, "critical": 25}[f["severity"]] for f in findings)
    return {"schema_version": "1.0", "engine_version": "0.1.0", "mode": "rules", "readiness": max(0, 100-penalty),
            "readiness_is_probability": False, "failure_probability": None, "findings": findings,
            "checks": checks, "graph": graph, "limitations": ["Static signals are incomplete; declarations are not proof of safety.", "No network, project scripts or planned commands were executed."]}
