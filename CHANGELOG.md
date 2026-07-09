# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and this project follows Semantic Versioning.

## [0.1.0] - 2026-07-09

### Added
- Initial production-style DotDoctor CLI skeleton using Typer + Rich + Pydantic.
- Layered architecture: CLI, application use-case, domain models, infrastructure checks.
- `scan` command with human-readable terminal report and JSON export.
- Exit code strategy:
  - `0`: only PASS
  - `1`: WARN present, no FAIL
  - `2`: FAIL present
  - `3`: DotDoctor runtime/config error
- Built-in checks for:
  - required binaries + minimum versions,
  - PATH integrity,
  - shell config sanity,
  - dev directory permissions.
- YAML config support with `python-dev` and `cpp-dev` profiles.
- Environment overrides (`DOTDOCTOR_CONFIG`, `DOTDOCTOR_DISABLE_CHECKS`).
- Unit and integration tests with edge-case coverage.
- GitHub Actions CI: ruff, black --check, mypy, pytest with coverage gate.
