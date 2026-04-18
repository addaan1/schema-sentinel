# Schema Sentinel

<p align="center">
  <img src="assets/banner.svg" alt="Schema Sentinel banner" width="100%" />
</p>

<p align="center">
  <strong>A CSV drift detector that explains what changed, how risky it is, and what to check next.</strong>
</p>

<p align="center">
  Current release: <strong>v0.2.0</strong> - Built for CSV snapshots, CI checks, and fast human review
</p>

<p align="center">
  <a href="https://github.com/addaan1/schema-sentinel/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-Apache_2.0-0f172a?style=for-the-badge&logo=apache&logoColor=white" alt="License"></a>
  <a href="https://github.com/addaan1/schema-sentinel"><img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.11+"></a>
  <a href="https://github.com/addaan1/schema-sentinel/actions/workflows/ci.yml"><img src="https://img.shields.io/badge/CI-GitHub_Actions-2088FF?style=for-the-badge&logo=githubactions&logoColor=white" alt="CI"></a>
  <img src="https://img.shields.io/badge/Reports-Markdown_%7C_HTML_%7C_JSON-0f766e?style=for-the-badge&logo=json&logoColor=white" alt="Reports">
</p>

Schema Sentinel compares two CSV snapshots and turns raw differences into a ranked, readable report. It is designed for data teams, ML pipelines, and anyone who wants a clear answer to a simple question: **did the data change, and does it matter?**

<table>
  <tr>
    <td align="center"><strong>Compare</strong><br />Two CSV snapshots side by side.</td>
    <td align="center"><strong>Score</strong><br />Risk from LOW to CRITICAL.</td>
    <td align="center"><strong>Share</strong><br />Markdown, HTML, and JSON outputs.</td>
  </tr>
</table>

<p align="center">
  <img src="assets/report-preview.svg" alt="Schema Sentinel report preview" width="100%" />
</p>

## Example Data

The bundled `examples/` folder is based on the Kaggle [Telco Customer Churn](https://www.kaggle.com/datasets/blastchar/telco-customer-churn) dataset.
The sample files are intentionally curated and trimmed so they stay small, but they still reflect a more realistic business table:

- mixed numeric and categorical columns
- service flags and contract fields
- a billing column with a noticeable value shift
- an added text feedback column in the newer snapshot
- a removed backup column to demonstrate schema drift

That makes the demo more useful than a tiny toy CSV while keeping the repository lightweight.

## Why It Exists

Most CSV diffs are technically correct but practically useless. Schema Sentinel focuses on the changes that usually cause real pain:

- schema breaks that can crash downstream jobs
- type changes that silently reshape your data
- null spikes that make features or dashboards unreliable
- category drift that introduces new values or removes old ones
- numeric drift that suggests behavior or distribution changes
- rename candidates that help you spot a column rebrand instead of a real deletion

## How It Works

1. You point Schema Sentinel at an old CSV and a new CSV.
2. It profiles both files column by column.
3. It matches similar columns, detects drift, and scores the risk.
4. It prints a terminal summary and writes report artifacts for sharing or automation.

## What You Get Back

| Output | Purpose |
| --- | --- |
| Terminal report | Fast feedback in the console and CI logs |
| `summary.md` | Easy to paste into GitHub issues, PRs, or artifacts |
| `report.html` | A polished visual report for reviewers |
| `report.json` | Machine-readable output for automation |

## What It Detects

| Signal | Why it matters |
| --- | --- |
| Added / removed columns | Usually the first sign of schema breakage |
| Rename suggestions | Helps separate true deletions from renamed fields |
| Type changes | Catches columns that changed from numeric to text, date to string, and more |
| Null-rate changes | Surfaces missing-data spikes before they spread |
| Unique-ratio changes | Highlights cardinality shifts and unstable columns |
| Constant columns | Flags fields that stopped changing or were accidentally flattened |
| Category drift | Detects new or disappearing discrete values |
| Numeric drift | Spots distribution shifts in numeric columns |
| Risk scoring | Converts many signals into `LOW`, `MEDIUM`, `HIGH`, or `CRITICAL` |

## Quick Start

Install the project locally with Python so the package lands in the active environment:

```bash
python -m pip install -e .[dev]
```

Run the built-in example comparison with Python first:

```bash
python -m schema_sentinel compare examples/old.csv examples/new.csv
```

This is the safest first command on Windows because it works even when the `schema-sentinel` console script is not on `PATH` yet.

After installation, the shorter console command also works:

```bash
schema-sentinel compare examples/old.csv examples/new.csv
```

Write every report format in one pass:

```bash
python -m schema_sentinel compare examples/old.csv examples/new.csv --format all
```

Send the reports to a custom folder:

```bash
python -m schema_sentinel compare examples/old.csv examples/new.csv --output-dir outputs
```

## Example Result

```text
Schema Sentinel
Comparing old.csv -> new.csv

Overall risk: CRITICAL
Stability score: 36/100

Top findings
- CRITICAL  Removed column `OnlineBackup`
- HIGH      Numeric drift detected in `MonthlyCharges`
- HIGH      Category drift detected in `Contract`

Reports written to:
- outputs/summary.md
- outputs/report.html
- outputs/report.json
```

## Configuration

Schema Sentinel auto-loads `config.json` from the current working directory when it exists. You can also point to a different file with `--config`.

Minimal example:

```json
{
  "output": {
    "directory": "outputs",
    "formats": ["markdown", "html", "json"],
    "fail_on": "high"
  },
  "matching": {
    "rename_threshold": 0.78
  }
}
```

Useful settings:

- `output.directory` controls where generated files are written
- `output.formats` can be `markdown`, `html`, `json`, `both`, or `all`
- `output.fail_on` sets the severity that should trigger exit code `2`
- `matching.rename_threshold` tunes how confident a rename suggestion must be

## CLI Reference

```bash
schema-sentinel compare <old.csv> <new.csv> [OPTIONS]
```

Options:

| Option | Meaning |
| --- | --- |
| `--config` | Load settings from a JSON config file |
| `--output-dir`, `-o` | Choose where report files are written |
| `--format`, `-f` | Select `markdown`, `html`, `json`, `both`, or `all` |
| `--fail-on` | Return exit code `2` when risk reaches the selected severity |

Exit codes:

- `0` means no findings or no risky drift
- `1` means findings exist, but they stay below the fail threshold
- `2` means critical drift or threshold-level risk was detected

## Build And Release

Install the packaging tools first, then build a local distribution:

```bash
python -m pip install build twine
python -m build
twine check dist/*
```

The repository also includes GitHub Actions for CI and release publishing so the project can be tested and packaged automatically.

## Development

Run the test suite:

```bash
pytest
```

Run linting:

```bash
ruff check .
```

## Troubleshooting

If you see `schema-sentinel : The term 'schema-sentinel' is not recognized`, the package is usually installed but the console script is not on `PATH` yet.

- Use `python -m schema_sentinel compare examples/old.csv examples/new.csv` as the reliable fallback.
- Make sure the same Python environment is active when you install and when you run the command.
- If you just installed the project, close and reopen PowerShell so the new PATH entry can refresh.

If `python` itself is not recognized on Windows:

- Install Python 3.11 or newer.
- Or disable the Windows App execution aliases for `python.exe` and `python3.exe`, then open a new terminal.

## Roadmap

- smarter profile matching for renamed columns
- additional file format support beyond CSV
- richer automation hooks for larger pipelines

## License

Released under the [Apache-2.0 License](LICENSE).
