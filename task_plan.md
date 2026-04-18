# Task Plan: Schema Sentinel v0.2 Expansion

## Goal
Turn the repository into a polished, production-ready open-source Python CLI that compares two CSV datasets, detects schema and drift risk, and generates Markdown, HTML, and JSON reports with a strong GitHub presentation.

## Current Phase
Phase 7

## Phases

### Phase 1: Requirements & Discovery
- [x] Understand user intent
- [x] Identify constraints and requirements
- [x] Document findings in findings.md
- **Status:** complete

### Phase 2: Planning & Structure
- [x] Define technical approach
- [x] Create project structure
- [x] Document decisions with rationale
- **Status:** complete

### Phase 3: Implementation
- [x] Build comparison engine
- [x] Build report generation
- [x] Build CLI and package metadata
- [x] Add examples, README, and license
- **Status:** complete

### Phase 4: Testing & Verification
- [x] Add and run automated tests
- [x] Verify outputs and CLI behavior
- [x] Fix issues found during verification
- **Status:** complete

### Phase 5: Delivery
- [x] Final review of deliverables
- [x] Ensure GitHub-ready documentation
- [x] Deliver summary to user
- **Status:** complete

### Phase 6: v0.2 Feature Expansion
- [x] Add `config.json` support and automatic config loading
- [x] Add JSON report output
- [x] Add rename suggestion and smarter column matching
- [x] Prepare GitHub/PyPI release packaging
- [x] Tighten `.gitignore` for generated artifacts
- **Status:** complete

### Phase 7: Verification & Delivery
- [x] Run pytest and lint checks after the v0.2 upgrade
- [x] Verify the CLI generates Markdown, HTML, and JSON artifacts
- [x] Update planning files and release notes
- [x] Deliver the completed work to the user
- **Status:** complete

## Key Questions
1. How should severity map to exit codes and failure behavior?
2. Which visual direction best fits the report-first UX?

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| Use Apache-2.0 | Matches user choice and keeps the project permissive. |
| Use a minimal Swiss + developer-tool visual style | Best balance of clarity, polish, and screenshot-friendly presentation. |
| Use deterministic heuristics instead of heavy statistical dependencies | Keeps the tool simple, portable, and easy to explain. |
| Use ASCII-safe CLI output | Prevents Windows console encoding failures. |
| Auto-load `config.json` from the working directory | Makes v0.2 feel natural while still allowing explicit overrides. |
| Keep build and publish dependencies out of the dev extra | Avoids local offline install issues while letting CI install them explicitly. |

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| `rtk git` could not resolve the workspace path with spaces | 1 | Switched to direct PowerShell commands for repository inspection. |
| `rtk proxy python` failed because Python launcher resolution is restricted here | 1 | Avoided relying on the UI-UX Python script and extracted guidance from the skill data files directly. |
| Typer CLI initially collapsed `compare` into the root command | 1 | Added an explicit command group so `schema-sentinel compare ...` works correctly. |
| Unicode arrow in the terminal header failed on Windows console encoding | 1 | Switched the CLI header to ASCII-safe `->`. |
| Editable install tried to fetch build isolation dependencies from the network | 1 | Used `--no-build-isolation` for local verification and moved build/publish tools out of the dev extra. |
| Editable install hit a permission error on the existing `__editable__` file | 1 | Verified the repo directly from source with `pytest` and `ruff` instead of reinstalling. |

## Notes
- Re-read this plan before major decisions.
- Keep changes deterministic and testable.
- Prioritize repository polish as much as code correctness.
