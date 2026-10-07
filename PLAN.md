# Tripwire Implementation Plan

## Assumptions

- `tripwire` is a Python project that will detect changes in Eero network state by comparing current device/router data against a saved baseline.
- Eero does not provide a formal public API for this use case, so the first version will use the existing Python client for the undocumented app API behind a narrow adapter.
- The first useful version should be a CLI tool, not a service or GUI.
- The current repository is a starter project, so the plan includes project structure, behavior, tests, and packaging work.

## Goals

- Provide a clear command-line workflow for initializing, checking, and updating an Eero network baseline.
- Store baseline data in a deterministic, inspectable format.
- Report added, removed, renamed, changed, and ungrouped devices clearly.
- Show which Eero group each device belongs to, with devices that belong to no group called out explicitly.
- Keep the implementation small, testable, and suitable for later extension.

## Non-Goals

- Real-time network monitoring.
- Replacing the Eero app for network administration.
- Remote synchronization or centralized reporting.
- Cryptographic signing of baselines in the first version.

## Milestone 1: Project Structure

- Replace the starter `main.py` with a package layout:
  - `src/tripwire/__init__.py`
  - `src/tripwire/cli.py`
  - `src/tripwire/scanner.py`
  - `src/tripwire/baseline.py`
  - `src/tripwire/reporting.py`
- Add tests under `tests/`.
- Configure `pyproject.toml` with package metadata, console script entry point, and test dependencies.

## Milestone 2: Programmatic Eero Access

- Use the existing Python `eero` client for the undocumented Eero app API as the first implementation path.
- Keep a minimal local implementation as a fallback only if the client cannot handle current authentication or required data retrieval.
- Document the risks of relying on an undocumented API:
  - Endpoints may change without notice
  - Authentication flows may break
  - Response shapes may drift
  - Account lockout or throttling behavior may be unclear
- Prototype authentication against a test Eero account using email or phone verification.
- Capture the minimum data needed for tripwire checks:
  - Networks
  - Eero nodes
  - Connected devices
  - Eero groups or profiles
  - Device names, IDs, MAC addresses, connection state, and node association where available
  - Device group/profile membership, including devices with no group/profile
- Wrap the `eero` client behind a local adapter interface so the rest of the app does not depend directly on the unofficial client library.
- Store session credentials outside the repository and document how to revoke them.
- Define failure behavior for expired sessions, MFA/login verification, rate limits, and unexpected response shapes.

## Milestone 3: Scanner

- Fetch current Eero network state through the adapter created in Milestone 2.
- Normalize network, node, and device records into an internal snapshot model.
- Normalize group/profile records and link each device to its group where the API exposes that relationship.
- Compare the current snapshot against a saved baseline.
- Detect added, removed, renamed, changed, regrouped, and ungrouped devices.
- Treat devices with no group/profile as a first-class report category, not as missing or invalid data.
- Treat unstable fields, such as signal strength or recent activity timestamps, as optional details rather than default tripwire failures.
- Include API/authentication errors in the report without corrupting the saved baseline.

## Milestone 4: CLI

- Implement commands:
  - `tripwire login`
  - `tripwire init --baseline BASELINE`
  - `tripwire check --baseline BASELINE`
  - `tripwire update --baseline BASELINE`
- Return non-zero exit codes when changes or scan errors are found.
- Provide machine-readable JSON output with `--json`.
- Keep default text output concise and grouped by change type.
- Include a group/profile column or section in default output, with a distinct `Ungrouped` value for devices that have no group.

## Milestone 5: Tests

- Unit test baseline serialization and schema version handling.
- Unit test snapshot comparison for added, removed, renamed, changed, regrouped, and ungrouped devices.
- Unit test adapter error handling with mocked Eero responses.
- Integration test the CLI commands using recorded or synthetic Eero payloads.
- Test ignored device IDs or MAC addresses if ignore support is added.
- Add regression tests for missing optional fields and unexpected response shapes.
- Add regression tests for devices with no group/profile and devices moving between groups/profiles.

## Milestone 6: Documentation

- Add a `README.md` with installation, quick start, command examples, and exit codes.
- Document baseline format and compatibility expectations.
- Include security limitations so users understand what this tool does and does not protect.

## Validation Checklist

- `python -m pytest` passes.
- `tripwire init` creates a stable baseline.
- `tripwire check` reports no changes immediately after initialization.
- Adding, removing, or renaming devices produces the expected report.
- Devices with no group/profile are listed explicitly as ungrouped.
- Updating the baseline clears intentional changes.

## Open Questions

- What maintenance threshold should trigger replacing the `eero` client with a minimal local implementation?
- Should baseline files support optional signing or encryption?
- Which device fields should count as meaningful drift versus noisy telemetry?
- Should ignores be based on device ID, MAC address, hostname, or all three?
- Should the tool support multiple Eero networks under one account?
- Does the Eero API expose the user's expected "group" concept as profiles, another grouping primitive, or both?
