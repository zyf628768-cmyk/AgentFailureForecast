# Release v0.1.0

Local release preparation does not publish to GitHub or PyPI. Choose the repository URL/maintainer identity before public publication.

1. Install `.[test]` and `build` in an isolated Python environment.
2. Run `python -m unittest discover -s tests -v`; preserve counts and skips.
3. Run all six CLI commands using the checked-in example plan and synthetic history. Render JSON, Markdown and HTML; validate schemas.
4. Run `python -m build`; inspect wheel and sdist contents for credentials, caches and local paths. Run `python scripts/verify_distribution.py` to rebuild the sdist, compare engine bytes and exercise a fresh offline wheel installation outside the source directory.
5. Install the wheel in a new environment with `pip install --no-index path/to/wheel.whl`. From outside the source directory run `forecast --version`, `--help` and all six commands against explicit example inputs.
6. Preserve `docs/validation.md`, check Git diff/status and package checksums. Run the CI matrix before claiming Linux/macOS compatibility.
7. Create a local source commit and annotated `v0.1.0` tag. Publish only with explicit user authorization. Enable private vulnerability reporting and choose repository settings when creating the public repository.

## Gated GitHub publication

The `reviewed-release` workflow only runs by manual dispatch, from `main` or the matching existing version tag. For a first release use `gh workflow run release.yml --ref main -f tag=v0.1.0 -f prerelease=true` or the Actions UI. The workflow refuses mismatched version/tag refs, runs the reusable test/install matrix on Windows, Ubuntu and macOS across Python 3.10–3.13, preserves per-job evidence, rebuilds and verifies distribution assets, then creates an exact annotated tag and GitHub Release. Existing tags pointing elsewhere are rejected rather than moved. Only the final job has repository write permission. It does not publish to PyPI. The MVP defaults to a prerelease.

For local asset preparation after committing/tagging, run `python scripts/package_release.py --tag v0.1.0 --output release-assets` from the project root. The output directory must not already exist. It requires a clean checkout at the tag, checks wheel/sdist source bytes and versions against that checkout, exports the tagged source zip, and produces SHA-256 checksums and provenance. It does not push or publish. Do not mark remote matrix results passed until actual jobs succeed; the publication notes append the workflow run URL after that gate passes.

Deliverable source archive includes SKILL.md, schemas, documentation and examples. The wheel installs only the Python engine; use the source archive/repository as the complete Skill bundle. The synthetic history generator is `scripts/generate_examples.py`; fixtures include no real user task records.
