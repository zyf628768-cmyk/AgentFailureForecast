"""Bounded local reads and best-effort report redaction. Never execute input."""
import json
import math
import os
import re
import stat
import tempfile
from pathlib import Path

MAX_BYTES = 2_000_000
SECRET = re.compile(r"(?i)(password|passwd|secret|token|api[_-]?key|authorization|credential|private[_-]?key)")


def redact(value):
    if isinstance(value, dict):
        return {k: "[REDACTED]" if SECRET.search(k) else redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, str):
        # Remove complete auth values before assignment redaction consumes only
        # the scheme name and accidentally leaves the actual credential behind.
        value = re.sub(r"(?i)\b(Bearer|Basic)\s+[^\s\"',;]+", r"\1 [REDACTED]", value)
        value = re.sub(r"(?i)\b([\w.-]*(?:password|passwd|secret|token|api[_-]?key|authorization|credential|access[_-]?key)[\w.-]*)\b[\"']?\s*[:=]\s*(?:\"[^\"]*\"|'[^']*'|[^\s,;&]+)", r"\1=[REDACTED]", value)
        value = re.sub(r"\b(?:sk-[A-Za-z0-9_-]{8,}|gh[pousr]_[A-Za-z0-9_]{8,}|AKIA[A-Z0-9]{16})\b", "[REDACTED]", value)
        value = re.sub(r"(?s)-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----", "[REDACTED]", value)
        return re.sub(r"(https?://)[^\s/@]+:[^\s/@]+@", r"\1[REDACTED]@", value)
    return value


def is_link(path):
    """Include Windows junction/reparse points on Python versions before 3.12."""
    try:
        metadata = Path(path).lstat()
    except FileNotFoundError:
        return False
    return stat.S_ISLNK(metadata.st_mode) or bool(getattr(metadata, "st_file_attributes", 0) & 0x400)


def safe_path(root, name):
    root = Path(root).resolve(strict=True)
    name = Path(name)
    if name.is_absolute() or name.drive or ".." in name.parts:
        raise ValueError("path must be relative without traversal")
    current = root
    for part in name.parts:
        current = current / part
        if is_link(current):
            raise ValueError("linked paths are not permitted")
    if not current.resolve().is_relative_to(root):
        raise ValueError("path escapes root")
    return current


def read_text(path):
    path = Path(path)
    if not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ValueError("input must be a regular file <= 2 MB")
    with path.open("rb") as stream:
        data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("input too large")
    return data.decode("utf-8-sig")


def parse_json(text):
    def pairs_hook(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON keys are not permitted")
            result[key] = value
        return result
    def invalid_constant(value):
        raise ValueError("nonfinite JSON numbers are not permitted")
    def finite_float(value):
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError("nonfinite JSON numbers are not permitted")
        return parsed
    return json.loads(text, object_pairs_hook=pairs_hook, parse_constant=invalid_constant, parse_float=finite_float)


def load_json(path):
    return parse_json(read_text(path))


def write_report(destination, text, force=False):
    """Never follow output links; replace the directory entry on --force."""
    destination = Path(destination).absolute()
    for path in (destination, *destination.parents):
        if is_link(path):
            raise ValueError("linked output rejected")
    if not force:
        with destination.open("x", encoding="utf-8") as stream:
            stream.write(text)
        return
    # In-place truncation would modify every name of a hard-linked file.
    # The temporary file is exclusive and stays on the destination filesystem.
    descriptor, temporary = tempfile.mkstemp(prefix=".forecast-", suffix=".tmp", dir=destination.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
