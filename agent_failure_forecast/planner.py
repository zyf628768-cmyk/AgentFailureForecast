"""Explicit JSON dependencies, plus sequential plain-text task import."""
from .rules import finding


def normalize(plan):
    if isinstance(plan, str):
        lines = [s.strip(" -*0123456789.\t") for s in plan.splitlines() if s.strip()]
        plan = {"goal": lines[0] if lines else "", "steps": [
            {"id": str(i + 1), "description": line, "depends_on": [str(i)] if i else []}
            for i, line in enumerate(lines)]}
    if not isinstance(plan, dict) or not isinstance(plan.get("steps", []), list):
        raise ValueError("plan must be an object with a steps array")
    steps = plan.get("steps", [])
    if not isinstance(plan.get("inputs", []), list) or any(not isinstance(x, str) for x in plan.get("inputs", [])):
        raise ValueError("inputs must be an array of strings")
    if len(steps) > 500:
        raise ValueError("at most 500 steps")
    ids = []
    declarations = len(plan.get("inputs", []))
    for step in steps:
        if not isinstance(step, dict) or not isinstance(step.get("id"), str) or not step["id"]:
            raise ValueError("each step needs a nonempty string id")
        ids.append(step["id"])
        if not isinstance(step.get("description", ""), str):
            raise ValueError("description must be a string")
        for field in ("depends_on", "tools", "paths", "env", "packages", "requires", "produces"):
            if not isinstance(step.get(field, []), list) or any(not isinstance(x, str) for x in step.get(field, [])):
                raise ValueError(field + " must be an array of strings")
            declarations += len(step.get(field, []))
            if declarations > 10000:
                raise ValueError("at most 10000 prerequisite/dependency declarations")
    if declarations > 10000:
        raise ValueError("at most 10000 prerequisite/dependency declarations")
    for step in steps:
        for field in ("reversible", "rollback", "backup", "timeout", "retries"):
            if field in step and not isinstance(step[field], bool):
                raise ValueError(field + " must be boolean")
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate step ids")
    if not isinstance(plan.get("goal", ""), str) or not isinstance(plan.get("acceptance", []), list) or any(not isinstance(x, str) for x in plan.get("acceptance", [])):
        raise ValueError("goal must be text; acceptance must be an array of strings")
    return plan


def build_graph(plan):
    plan = normalize(plan)
    steps = plan.get("steps", [])
    ids = [s["id"] for s in steps]
    edges, issues = [], []
    def issue(rid, message):
        issues.append(finding(rid, "task", "high", message, "Execution ordering may fail", "Review dependency graph", "Declare prerequisites and reorder steps"))
    deps = {s["id"]: s.get("depends_on", []) for s in steps}
    for step in steps:
        for dep in deps[step["id"]]:
            edges.append({"from": dep, "to": step["id"]})
            if dep not in deps:
                issue("PLAN001", "Missing prerequisite step")
            elif ids.index(dep) >= ids.index(step["id"]):
                issue("PLAN002", "Listed order precedes a dependency")
    remaining = set(ids)
    order = []
    while remaining:
        ready = [i for i in ids if i in remaining and all(d in order for d in deps[i])]
        if not ready:
            break
        order.extend(ready)
        remaining.difference_update(ready)
    # Separate real cycles from nodes merely blocked by missing dependencies.
    pending_nodes, processed = set(ids), set()
    while pending_nodes:
        ready = {i for i in pending_nodes if all(d in processed or d not in deps for d in deps[i])}
        if not ready:
            break
        processed.update(ready)
        pending_nodes.difference_update(ready)
    cyclic = bool(pending_nodes)
    if cyclic:
        issue("PLAN003", "Dependency cycle detected")
    for step in steps:
        ancestors = set()
        pending = list(deps[step["id"]])
        while pending:
            dep = pending.pop()
            if dep in ancestors or dep not in deps:
                continue
            ancestors.add(dep)
            pending.extend(deps[dep])
        available = set(plan.get("inputs", []))
        for s in steps:
            if s["id"] in ancestors:
                available.update(s.get("produces", []))
        if set(step.get("requires", [])) - available:
            issue("PLAN004", "Required artifact lacks an ancestor producer or declared input")
    return {"nodes": ids, "edges": edges, "topological_order": order, "cyclic": cyclic, "findings": issues}
