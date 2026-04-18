# Findings & Decisions

## Requirements
- Build a Python CLI named `schema-sentinel` for comparing two CSV files.
- Detect schema changes, type changes, null-rate changes, category drift, numeric drift, and likely renames.
- Generate CLI output, `summary.md`, `report.html`, and `report.json`.
- Add a GitHub-ready README and Apache-2.0 license.
- Include example datasets, tests, CI, and release packaging.

## Research Findings
- The repository started as documentation-only, with no implementation files in place.
- The UI/UX direction that fits best is minimal Swiss / developer-tool: high contrast, clear hierarchy, and strong report readability.
- The report should be scan-first and severity-first, with a strong hero area and compact summary cards.
- The project can stay lightweight by using deterministic heuristics instead of heavy statistical dependencies.
- Windows console encoding can break on Unicode arrows in `rich` output, so the terminal header should stay ASCII-safe.
- Typer needs an explicit command-group structure to preserve the requested `schema-sentinel compare ...` UX.
- `config.json` is best auto-loaded from the working directory, with an explicit `--config` override for power users.
- JSON output is most useful when it shares the same context model as Markdown and HTML.
- Build and publish tooling should stay out of the dev extra in this environment so local offline installs do not fail.

## Technical Decisions
| Decision | Rationale |
|----------|-----------|
| Use `typer` for the CLI | Clean subcommand support and good developer ergonomics. |
| Use `pandas` for CSV loading and profiling | Reliable tabular processing with reasonable defaults. |
| Use `rich` for terminal output | Makes the CLI feel polished and easier to scan. |
| Use `jinja2` for report templates | Keeps HTML and Markdown rendering maintainable. |
| Use `Apache-2.0` license | Explicitly confirmed by the user. |
| Use ASCII-safe CLI headers | Prevents terminal crashes on cp1252 Windows consoles. |
| Auto-load `config.json` when present | Gives the v0.2 CLI a natural default configuration story. |
| Keep `build` and `twine` out of the dev extra | Avoids offline/local editable-install issues while still supporting CI and release workflows. |

## Issues Encountered
| Issue | Resolution |
|-------|------------|
| `rtk` wrapper did not work cleanly with `git` in this workspace | Used direct PowerShell commands for inspection instead. |
| Python UI-UX script launcher was blocked by the Windows Store alias | Pulled design guidance from the skill data files manually. |
| Typer initially behaved like a single root command | Reworked the CLI into a proper `compare` command group. |
| Windows console rejected a Unicode arrow in the CLI header | Replaced it with `->`. |
| Editable install tried to resolve build dependencies over a restricted network | Used `--no-build-isolation` locally and installed build tools explicitly in the CI/release workflows. |
| Editable install hit a permission error on the existing `__editable__` file in user site-packages | Verified the repo directly from source with `pytest` and `ruff` instead of reinstalling. |

## Resources
- `README.md`
- `PRD.md`
- `DESIGN_UI_UX_SPEC.md`
- `config.json`
- `.github/workflows/release.yml`
- `C:\Users\adief\.codex\skills\ui-ux-pro-max\data\products.csv`
- `C:\Users\adief\.codex\skills\ui-ux-pro-max\data\styles.csv`
- `C:\Users\adief\.codex\skills\ui-ux-pro-max\data\typography.csv`
- `C:\Users\adief\.codex\skills\ui-ux-pro-max\data\colors.csv`
- `C:\Users\adief\.codex\skills\ui-ux-pro-max\data\ux-guidelines.csv`

## Visual/Browser Findings
- No browser-based mockups were generated in this phase.
- The chosen visual tone should emphasize trust, clarity, and report readability over decoration.
