# Product Requirements Document (PRD)
## Project: Schema Sentinel
## Version: Draft v0.1
## Owner: Sahrul Adicandra
## Status: Initial Planning

---

## 1. Product Summary

Schema Sentinel is a lightweight open-source tool for detecting schema and data drift between two tabular datasets, starting with CSV files. The product compares an old dataset and a new dataset, identifies risky changes, classifies their severity, and produces developer-friendly reports.

The goal is to help users catch breakage early before changed datasets disrupt analytics, training pipelines, dashboards, or downstream applications.

---

## 2. Problem Statement

In many data workflows, users replace one dataset version with another without a clear comparison step. This creates avoidable problems such as:
- missing columns,
- renamed columns,
- broken data types,
- sudden spikes in missing values,
- category changes,
- and unexpected distribution changes.

Most lightweight workflows do not have a simple, visual, open-source tool that gives a fast answer to this question:

**“Is this new dataset safe to use?”**

Schema Sentinel exists to answer that question quickly.

---

## 3. Product Vision

Build a polished open-source dataset comparison tool that feels simple enough for students but useful enough for real workflows.

The long-term vision is to make Schema Sentinel a practical safeguard step in dataset handoffs, data cleaning pipelines, and CI validation.

---

## 4. Goals

### 4.1 Primary Goals
- Compare two dataset versions with a simple CLI interface
- Detect schema changes and quality drift quickly
- Surface the most dangerous issues first
- Produce reports that are both machine-usable and human-readable
- Be easy to install, easy to demo, and easy to contribute to

### 4.2 Secondary Goals
- Make the project visually strong for GitHub sharing
- Support future CI usage via exit codes and config files
- Create a strong portfolio-grade open-source repo

---

## 5. Non-Goals (v1)

The following are explicitly out of scope for the first release:
- real-time monitoring dashboards,
- database connectors,
- streaming data support,
- advanced anomaly detection,
- enterprise observability features,
- complex policy engines,
- collaborative web app UI.

---

## 6. Target Users

### Primary Users
- Data science students
- Analysts working with recurring CSV exports
- Open-source users interested in data quality tooling

### Secondary Users
- Data engineers validating dataset updates
- ML practitioners checking training data changes
- Maintainers who want CI-friendly dataset validation

---

## 7. User Stories

### Core User Stories
1. As a data science student, I want to compare two CSV files so I can understand what changed without manually checking every column.
2. As an analyst, I want to know whether null rates or category values changed significantly before I update my dashboard inputs.
3. As a maintainer, I want a CLI exit code so I can fail CI when critical dataset drift is detected.
4. As a project viewer on GitHub, I want a clear HTML report so I can immediately understand the value of the tool.

### Stretch User Stories
5. As a user, I want to ignore known-safe columns in a config file.
6. As a user, I want dimensional risk breakdowns so I can see exactly where the dataset became worse.
7. As a user, I want a machine-readable JSON report so I can integrate this tool into automation later.

---

## 8. Key Use Cases

### Use Case A: Manual comparison
A user runs:

```bash
schema-sentinel compare old.csv new.csv
```

The tool prints a terminal summary and generates a Markdown and HTML report.

### Use Case B: Pre-deployment validation
A team compares yesterday’s dataset with today’s dataset before replacing an artifact in production.

### Use Case C: CI gate
A project uses Schema Sentinel in GitHub Actions. If critical changes are found, the build fails.

---

## 9. Functional Requirements

### 9.1 Input
The system must:
- accept two CSV file paths as input,
- validate file existence,
- validate readable CSV structure,
- provide understandable error messages.

### 9.2 Schema Comparison
The system must:
- detect added columns,
- detect removed columns,
- detect type changes,
- detect row and column count changes.

### 9.3 Data Drift Checks
The system must:
- compare missing-value rates per column,
- compare unique ratios,
- detect constant-column changes,
- detect categorical value changes,
- perform basic numeric distribution comparisons for numeric columns.

### 9.4 Risk Classification
The system must:
- assign severity levels to findings,
- summarize overall risk,
- surface the highest-risk issues first,
- return an exit code appropriate for automation.

### 9.5 Reporting
The system must:
- print concise CLI summaries,
- generate `summary.md`,
- generate `report.html`,
- structure results in a way that can later support JSON export.

---

## 10. Non-Functional Requirements

The product should:
- be installable with minimal dependencies,
- run locally on normal laptop-sized CSV files,
- have readable code structure,
- be testable with pytest,
- be visually clean enough for documentation and screenshots,
- support future extension without major rewrites.

---

## 11. Success Metrics

### MVP Success Metrics
- User can compare two CSV files in one command
- Report clearly identifies major schema changes
- HTML report is understandable without reading code
- README demonstrates value in under one minute
- Local execution works reliably on sample datasets

### Open-Source Success Signals
- The repo is easy to clone and run
- The project gets stars, forks, or issue engagement
- Contributors can identify clear improvement areas
- Viewers understand the project from screenshots and report outputs

---

## 12. Constraints

- Keep the first version simple and deterministic
- Avoid adding too many dependencies early
- Prioritize report clarity over statistical sophistication
- Prefer rules that are easy to explain in README and code

---

## 13. Risks

### Product Risks
- Reports may feel useful in demos but too generic for real datasets
- Risk scoring may be perceived as arbitrary
- Overly strict thresholds could create noisy warnings

### Execution Risks
- Scope may expand too quickly
- UI/report polish may consume too much implementation time
- Drift detection logic may become complex before the MVP is stable

---

## 14. MVP Scope Definition

### Included in MVP
- compare command
- CSV input support
- schema diff
- null-rate comparison
- basic type-change detection
- simple risk engine
- Markdown summary
- HTML report
- exit codes

### Excluded from MVP
- YAML config
- Parquet support
- folder compare
- semantic column matching
- web app
- advanced dashboards

---

## 15. Future Versions

### v0.2.0
- `config.json`
- ignored columns
- required columns
- dimensional health split
- better threshold customization

### v0.3.0
- JSON output
- GitHub Actions example
- compare folders
- better rename suggestions

### v1.0.0
- more explainable risk engine
- more robust drift checks
- stronger automation integration
- optional support for additional file types

---

## 16. Open Questions

- How should overall risk be calculated in a way that feels intuitive?
- Should warnings be purely threshold-based at first, or partially role-aware?
- How much numeric drift logic is enough for v1 without overcomplicating implementation?
- Should rename suggestions be in scope before v1 or after?

---

## 17. Release Criteria for v0.1.0

The MVP is ready to release when:
- compare command works end-to-end,
- at least one example dataset pair is included,
- Markdown and HTML reports generate correctly,
- tests cover core comparison logic,
- README clearly explains setup and usage,
- the tool can be demoed in under 60 seconds.
