# Release Checklist

## Versioning
- [ ] Version bumped according to SemVer in `pyproject.toml`.
- [ ] Changelog updated with release date and notable changes.

## Quality gates
- [ ] `ruff check .`
- [ ] `black --check .`
- [ ] `mypy src`
- [ ] `pytest --cov=src/dotdoctor --cov-fail-under=75`

## Product checks
- [ ] `dotdoctor scan` runs successfully on Linux.
- [ ] `dotdoctor scan --profile cpp-dev` runs successfully.
- [ ] JSON export works and schema is stable.
- [ ] Exit codes validated on pass/warn/fail/runtime-error paths.

## Portfolio packaging
- [ ] README updated (problem, architecture, limits, roadmap).
- [ ] Demo script validated (happy path + failure path).
- [ ] Example JSON report refreshed if format changed.

## Release process
- [ ] Tag created (`vX.Y.Z`).
- [ ] Release notes include migration notes (if needed).
- [ ] CI green on main branch.
