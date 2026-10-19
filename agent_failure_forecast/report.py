"""Reports never render untrusted HTML or raw task descriptions."""
import html
import json
from .safety import redact


def render(result, format="json"):
    result = redact(result)
    serialized = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False)
    if format == "json":
        return serialized + "\n"
    if format == "html":
        return '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>AgentFailureForecast</title><h1>AgentFailureForecast</h1><pre>' + html.escape(serialized) + "</pre></html>\n"
    if format == "markdown":
        # JSON inside a fenced block remains data; escape possible fence delimiters.
        return "# AgentFailureForecast\n\nReadiness is a heuristic, not failure probability.\n\n```json\n" + serialized.replace("`", "\\u0060") + "\n```\n"
    raise ValueError("unknown report format")
