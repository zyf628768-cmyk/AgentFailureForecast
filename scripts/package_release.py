"""Package a clean, tagged, already-built release; never publish or push."""
import argparse
from email.parser import Parser
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--dist", type=Path, default=Path("dist"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"v\d+\.\d+\.\d+", args.tag):
        raise ValueError("expected a stable vMAJOR.MINOR.PATCH tag")
    root = Path(__file__).resolve().parents[1]
    def git(*arguments):
        return subprocess.run(["git", "-c", "safe.directory="+str(root), "-C", root, *arguments],
                              capture_output=True, text=True, check=True, timeout=30).stdout.strip()
    commit = git("rev-parse", "HEAD")
    if git("rev-parse", args.tag+"^{commit}") != commit or git("status", "--porcelain"):
        raise ValueError("release requires a clean checkout at the selected tag")
    wheels = list(args.dist.glob("*.whl"))
    sources = list(args.dist.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sources) != 1:
        raise ValueError("dist needs exactly one wheel and one sdist")
    with zipfile.ZipFile(wheels[0]) as wheel:
        name = next(n for n in wheel.namelist() if n.endswith(".dist-info/METADATA"))
        version = Parser().parsestr(wheel.read(name).decode())["Version"]
        if "v"+version != args.tag:
            raise ValueError("wheel version and selected tag differ")
        for name in wheel.namelist():
            if name.startswith("agent_failure_forecast/") and name.endswith(".py"):
                if wheel.read(name) != (root/name).read_bytes():
                    raise ValueError("wheel does not match the tagged source")
    with tarfile.open(sources[0]) as source:
        metadata = next(m for m in source.getmembers() if m.name.count("/")==1 and m.name.endswith("/PKG-INFO"))
        if Parser().parsestr(source.extractfile(metadata).read().decode())["Version"] != version:
            raise ValueError("source distribution version differs from wheel")
        for member in source.getmembers():
            if member.isfile() and "/agent_failure_forecast/" in member.name and member.name.endswith(".py"):
                relative = "agent_failure_forecast/"+member.name.split("/agent_failure_forecast/", 1)[1]
                if source.extractfile(member).read() != (root/relative).read_bytes():
                    raise ValueError("source distribution does not match the tagged source")
    args.output.mkdir(parents=True, exist_ok=False)
    archive = args.output/("agent-failure-forecast-"+args.tag+"-source.zip")
    git("archive", "--format=zip", "--prefix=agent-failure-forecast/", "--output="+str(archive.resolve()), args.tag)
    for artifact in [wheels[0], sources[0], root/"docs"/"release-notes-v0.1.0.md"]:
        shutil.copy2(artifact, args.output/artifact.name)
    provenance = {"tag": args.tag, "commit": commit, "version": version, "scope": "locally assembled; CI results are separate workflow artifacts"}
    (args.output/"provenance.json").write_text(json.dumps(provenance, indent=2)+"\n", encoding="utf-8")
    for name in ("release-verification.json",):
        path = root/name
        if path.exists():
            shutil.copy2(path, args.output/name)
    files = sorted(p for p in args.output.iterdir() if p.is_file())
    checksums = "".join(hashlib.sha256(p.read_bytes()).hexdigest()+"  "+p.name+"\n" for p in files)
    (args.output/"SHA256SUMS").write_text(checksums, encoding="utf-8")
    print(json.dumps(provenance))


if __name__ == "__main__":
    main()
