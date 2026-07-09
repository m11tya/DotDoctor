# Contributing

Thanks for contributing to DotDoctor.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

## Quality checks

```bash
ruff check .
black --check .
mypy src
pytest --cov=src/dotdoctor --cov-fail-under=75
```

## Commit style

Use meaningful commits, for example:
- feat(checks): add shell PATH anomaly detector
- fix(cli): handle invalid profile with exit code 3
- docs(readme): add architecture and demo section

## Pull requests

Before opening a PR:
- run all quality checks locally,
- update README/CHANGELOG when behavior changes,
- add tests for bug fixes and new checks.
