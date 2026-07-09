# DotDoctor Portfolio Pitch

## 30-second pitch

DotDoctor is a Linux CLI diagnostics tool that detects common development environment failures before they break productivity. It validates required binaries, minimum versions, PATH health, shell config quality, and directory permissions, then returns both a human-readable report and machine-readable JSON with reliable exit codes for automation.

## Problems solved

- "Works on my machine" inconsistencies.
- Toolchain drift over time.
- Hidden shell/PATH misconfigurations.
- Permission errors discovered too late in builds.

## Engineering highlights

- Layered architecture (CLI/application/domain/infrastructure).
- Unified check interface for extensibility.
- Robust error handling with continue-on-error scan strategy.
- Test coverage gate with CI quality checks.

## Admission-friendly talking points

- Demonstrates systems thinking: diagnosis pipeline + predictable exit semantics.
- Demonstrates reliability focus: edge-case handling and explicit remediation.
- Demonstrates software engineering maturity: typing, linting, tests, CI, changelog, release checklist.

## Suggested demo flow (2-4 minutes)

1. Show default run (`dotdoctor`) and explain summary/exit code.
2. Show JSON export and machine-readable details.
3. Show a warning/failure case and remediation guidance.
4. Explain architecture and why business logic is not in CLI layer.
