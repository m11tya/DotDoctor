# DotDoctor

DotDoctor is a Linux-first CLI tool that diagnoses development environment issues before they derail your workflow.

## GitHub About (recommended)

- Tagline:
  Linux-first CLI doctor for dev environment diagnostics with actionable remediation.
- Description:
  DotDoctor scans your Linux development setup, validates toolchain/version/path/shell/permissions,
  and outputs both human-readable and machine-readable reports with reliable exit codes.
- Topics:
  `python`, `cli`, `devops`, `linux`, `diagnostics`, `developer-tools`, `typer`, `rich`, `pydantic`, `quality-assurance`

## Problem statement

Developers (especially students and juniors) regularly lose hours because local environments silently drift:
- tools disappear from `PATH`,
- binary versions become outdated,
- shell config accumulates risky entries,
- permission issues break builds.

DotDoctor turns these hidden problems into clear diagnostics with actionable remediation.

## Why this matters

- Faster onboarding and fewer "works on my machine" moments.
- Safer pre-flight checks before coding sessions and interviews.
- Better confidence in Linux setup reliability.

## Features (MVP)

- `scan` command for environment diagnostics.
- Structured check output: `PASS`, `WARN`, `FAIL`.
- Human-readable terminal report (Rich table).
- Machine-readable JSON export.
- Predictable exit codes:
  - `0`: only PASS
  - `1`: WARN exists, no FAIL
  - `2`: FAIL exists
  - `3`: DotDoctor runtime/config error
- Configurable checks and profiles (`python-dev`, `cpp-dev`).

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
dotdoctor scan
```

## Usage

```bash
# one-command scan with live fullscreen interface
dotdoctor

# default profile (python-dev)
dotdoctor scan

# explicit profile
dotdoctor scan --profile cpp-dev

# force live interface for scan command
dotdoctor scan --ui

# export JSON report
dotdoctor scan --json-output artifacts/report.json

# custom config file
dotdoctor scan --config dotdoctor.example.yml

# disable specific checks for one run
dotdoctor scan --disable-check shell.config --disable-check permissions.dev_dirs
```

## Config

- Default config path: `dotdoctor.yml`
- Override config path: `DOTDOCTOR_CONFIG=/path/to/file.yml`
- Disable checks via env: `DOTDOCTOR_DISABLE_CHECKS=check.id,check.id`

See [dotdoctor.example.yml](dotdoctor.example.yml) for the full schema.

## Architecture overview

Layered design keeps business rules isolated from I/O and CLI concerns:

- `CLI` layer: argument parsing, output, exit signaling.
- `Application` layer: orchestrates checks via use-cases.
- `Domain` layer: core models and contracts (`CheckResult`, `ScanReport`, check interface).
- `Infrastructure` layer: concrete checks, subprocess, filesystem, YAML loading.

### Why this design

- Easy to add new checks without touching CLI flow.
- Testable core logic with low coupling.
- Safer scaling toward plugin architecture later.

### Trade-offs

- Slightly more boilerplate than a single-file script.
- Requires discipline to keep boundaries clean.

## Current checks

- Binary availability and minimum version checks for required tools.
- PATH integrity checks (empty segments, duplicates, missing dirs).
- Shell config sanity checks.
- Permissions checks for development directories.

## Demo scenarios

### Happy path

```bash
dotdoctor scan --profile python-dev --json-output artifacts/happy.json
echo $?
```

### Failure path

```bash
dotdoctor scan --profile cpp-dev --disable-check path.integrity --json-output artifacts/failure.json
echo $?
```

## Terminal demo recording commands

Option 1 (script):

```bash
script -q artifacts/demo-session.txt
dotdoctor scan --profile python-dev
dotdoctor scan --profile cpp-dev --json-output artifacts/cpp.json
exit
```

Option 2 (asciinema if installed):

```bash
asciinema rec artifacts/dotdoctor-demo.cast
dotdoctor scan --profile python-dev
dotdoctor scan --profile cpp-dev --json-output artifacts/cpp.json
exit
```

## Example JSON report

See [artifacts/example-report.json](artifacts/example-report.json).

## Engineering process

- Semantic Versioning (SemVer).
- Changelog: [CHANGELOG.md](CHANGELOG.md).
- CI pipeline: lint + type-check + tests + coverage gate.
- Release checklist: [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md).

## Limitations

- Linux-first scope (no Windows/macOS support yet).
- No auto-fix mode (diagnostics only).
- No parallel check execution yet.

## Roadmap

1. Plugin system via entry points.
2. Optional autofix mode for safe remediations.
3. More shell detectors and distro-specific checks.
4. Performance profiling and parallel execution.
5. JSON schema versioning for report stability.

## What I learned

1. Exit code contracts are as important as terminal UX in CLI tooling.
2. Continue-on-error diagnostics provide much more value than fail-fast scans.
3. Version parsing needs defensive logic because tool outputs are inconsistent.
4. Layered architecture pays off quickly once checks start growing.
5. Small design choices in config schema strongly affect extensibility.
6. Fast CI feedback (lint/type/tests) prevents hidden regressions.
7. Edge-case tests are critical for filesystem and PATH-heavy tools.

## Future improvements (prioritized)

1. Add plugin loading and dynamic check discovery.
2. Introduce stable report schema version and migration policy.
3. Add distro-specific remediation commands (Arch, Ubuntu, Fedora).
4. Improve shell check heuristics to reduce false positives.
5. Add optional telemetry-free timing metrics per check.
6. Add richer integration tests with fixture-based fake toolchains.
