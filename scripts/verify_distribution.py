"""Offline release round-trip checks. Requires the documented dev dependencies.

Run after python -m build. No inspected project command is ever executed by the
engine; this separate maintainer script explicitly builds our own release.
"""
import argparse
import json
import importlib.metadata
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile
import tempfile
import venv
import zipfile


def run(args, cwd, env, expected=0):
    result = subprocess.run(list(map(str, args)), cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8", timeout=120)
    if result.returncode != expected:
        raise RuntimeError("Distribution acceptance failed: " + result.stderr[-4000:])
    return result.stdout


def extract_source(archive, destination):
    total = 0
    with tarfile.open(archive) as source:
        members = source.getmembers()
        if len(members) > 1000:
            raise ValueError("too many source members")
        for member in members:
            parts = PurePosixPath(member.name)
            if parts.is_absolute() or ".." in parts.parts or "\\" in member.name or ":" in member.name or not (member.isfile() or member.isdir()):
                raise ValueError("unsafe source member")
            total += member.size
            if total > 50_000_000:
                raise ValueError("source archive too large")
            target = destination.joinpath(*parts.parts)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with source.extractfile(member) as stream, target.open("xb") as output:
                    output.write(stream.read())
    roots = list(destination.iterdir())
    if len(roots) != 1 or not roots[0].is_dir():
        raise ValueError("source archive needs one project root")
    return roots[0]


def python_files(wheel):
    with zipfile.ZipFile(wheel) as archive:
        return {name: archive.read(name) for name in archive.namelist() if name.startswith("agent_failure_forecast/") and name.endswith(".py")}


def validate_build_backend():
    try:
        major = int(importlib.metadata.version("setuptools").split(".")[0])
    except (importlib.metadata.PackageNotFoundError, ValueError):
        major = 0
    if major < 77:
        raise ValueError('Offline rebuild requires setuptools>=77; install build "setuptools>=77" wheel in the development environment first')


def main():
    parser = argparse.ArgumentParser(description="Verify sdist round-trip, offline wheel installation and all CLI commands")
    parser.add_argument("--dist", type=Path, default=Path("dist"))
    parser.add_argument("--output", type=Path, help="Explicit JSON evidence destination")
    args = parser.parse_args()
    validate_build_backend()
    wheels = list(args.dist.resolve().glob("*.whl"))
    sources = list(args.dist.resolve().glob("*.tar.gz"))
    if len(wheels) != 1 or len(sources) != 1:
        raise ValueError("dist must contain exactly one wheel and one sdist")
    env = {k: v for k, v in os.environ.items() if k.upper() not in ("PYTHONPATH", "PYTHONHOME")}
    env["PYTHONIOENCODING"] = "utf-8"
    commands = []
    with tempfile.TemporaryDirectory(prefix="forecast-distribution-") as folder:
        temporary = Path(folder).resolve()
        source_root = temporary/"source"
        source_root.mkdir()
        project = extract_source(sources[0], source_root)
        required = ["SKILL.md", "README.md", "README.zh-CN.md", "schemas/report.schema.json", "tests/test_review.py", "docs/test-results.txt", ".github/workflows/tests.yml", "scripts/verify_distribution.py"]
        if not all((project/name).is_file() for name in required):
            raise ValueError("incomplete source distribution")
        run([sys.executable, "-m", "build", "--wheel", "--no-isolation", "--outdir", temporary/"roundtrip"], project, env)
        rebuilt = next((temporary/"roundtrip").glob("*.whl"))
        if python_files(wheels[0]) != python_files(rebuilt):
            raise ValueError("sdist round-trip changed engine source")
        with zipfile.ZipFile(wheels[0]) as archive:
            metadata_name = next(n for n in archive.namelist() if n.endswith(".dist-info/METADATA"))
            requirements = [line for line in archive.read(metadata_name).decode().splitlines() if line.startswith("Requires-Dist:")]
            if any('extra == "test"' not in line for line in requirements):
                raise ValueError("unexpected runtime dependency")
        environment = temporary/"venv"
        venv.EnvBuilder(with_pip=False).create(environment)
        binary = environment/("Scripts" if os.name == "nt" else "bin")
        python = binary/("python.exe" if os.name == "nt" else "python")
        executable = binary/("forecast.exe" if os.name == "nt" else "forecast")
        run([sys.executable, "-m", "pip", "--python", python, "install", "--no-index", "--no-deps", wheels[0]], temporary, env)
        module = run([python, "-I", "-c", "import agent_failure_forecast; print(agent_failure_forecast.__file__)"], temporary, env).strip()
        if not Path(module).resolve().is_relative_to(environment):
            raise ValueError("import came from outside the fresh environment")
        examples = project/"examples"
        common = ["--plan", examples/"plan.json", "--root", project]
        for command in ("scan", "plan", "simulate", "predict"):
            result = json.loads(run([executable, command, *common], temporary, env))
            if not isinstance(result, dict):
                raise ValueError("invalid command output")
            commands.append(command)
        policy = temporary/"policy-report.json"
        run([executable, "scan", *common, "--fail-on", "high", "--output", policy], temporary, env, expected=3)
        if not json.loads(policy.read_text(encoding="utf-8"))["findings"]:
            raise ValueError("severity policy did not preserve its report")
        commands.append("scan --fail-on high (expected exit 3)")
        prediction = json.loads(run([executable, "predict", *common, "--history", examples/"history.synthetic.json", "--as-of", "2026-01-01T00:00:00Z"], temporary, env))
        if prediction["mode"] != "statistical":
            raise ValueError("synthetic probability mechanism did not run")
        commands.append("predict --history (synthetic)")
        backtest = json.loads(run([executable, "backtest", "--history", examples/"history.synthetic.json"], temporary, env))
        if len(backtest["folds"]) != 3:
            raise ValueError("invalid backtest output")
        commands.append("backtest")
        for format in ("json", "markdown", "html"):
            text = run([executable, "report", "--input", examples/"scan.json", "--format", format], temporary, env)
            if not text.strip():
                raise ValueError("empty rendered report")
            commands.append("report --format "+format)
        for command in (None, "scan", "plan", "simulate", "predict", "backtest", "report"):
            run([executable, *([command] if command else []), "--help"], temporary, env)
            commands.append((command+" " if command else "")+"--help")
        version = run([executable, "--version"], temporary, env).strip()
        commands.append("--version")
    evidence = {"version": version, "sdist_roundtrip": "passed; engine Python files byte-identical", "source_manifest": "passed", "fresh_offline_wheel_install": "passed", "runtime_dependencies": [], "import_outside_source": "passed", "cli_invocations": len(commands), "commands": commands, "synthetic_only": True}
    text = json.dumps(evidence, indent=2)+"\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
