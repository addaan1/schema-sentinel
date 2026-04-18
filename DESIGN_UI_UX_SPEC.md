# Design Document / UI UX Spec
## Project: Schema Sentinel
## Version: Draft v0.1

---

## 1. Design Goals

The UI/UX of Schema Sentinel should feel:
- clear,
- developer-friendly,
- modern,
- visually strong enough for screenshots,
- and fast to understand even for first-time users.

This is not a dashboard product. It is a report-first tool. The output should help a user answer these questions quickly:
1. What changed?
2. How risky is it?
3. What should I do next?

---

## 2. Primary Surfaces

Schema Sentinel v0.1 has three main user experience surfaces:

### A. CLI Output
Purpose:
- fast summary,
- immediate feedback,
- CI-compatible status.

### B. Markdown Report (`summary.md`)
Purpose:
- readable in GitHub,
- easy to save with artifacts,
- easy to include in issues or PRs.

### C. HTML Report (`report.html`)
Purpose:
- polished visual output,
- good for sharing and screenshots,
- deeper inspection of findings.

---

## 3. UX Principles

### 3.1 Scan-first layout
The report should be understandable in seconds, not minutes.
Important information must appear high on the page.

### 3.2 Severity-first organization
Users care most about dangerous changes. Critical and high-severity findings should always appear before informational details.

### 3.3 Explain, do not overwhelm
Avoid overly technical visuals in early versions. Prefer simple labels, concise descriptions, and clear next steps.

### 3.4 Screenshot-friendly composition
The top section of the HTML report should look good when cropped into a README image or social preview.

### 3.5 Consistent terminology
Use stable language throughout the product:
- Added Columns
- Removed Columns
- Type Changes
- Null Rate Delta
- Category Drift
- Numeric Drift
- Overall Risk

---

## 4. CLI UX Spec

### 4.1 Command format

```bash
schema-sentinel compare old.csv new.csv
```

### 4.2 CLI behavior
The CLI should:
- validate inputs quickly,
- print a concise summary,
- write artifact files,
- return a clear exit code.

### 4.3 CLI output structure
Recommended terminal output order:

1. Header
2. Files compared
3. Overview stats
4. Top risk findings
5. Output paths
6. Exit code summary

### 4.4 Example CLI output

```text
Schema Sentinel
===============
Comparing: old.csv -> new.csv

Rows: 10,000 -> 10,450
Columns: 12 -> 13

Added columns: 1
Removed columns: 1
Type changes: 2
Critical issues: 1
High issues: 2

Overall risk: HIGH
Reports written to: outputs/
Exit code: 2
```

### 4.5 CLI writing style
- concise
- high signal
- avoid long paragraphs
- highlight counts and severity levels

---

## 5. Markdown Report UX Spec

### 5.1 Purpose
The Markdown report should work well inside GitHub, code reviews, issues, and artifacts.

### 5.2 Required sections
1. Title
2. Compared files
3. Overall risk
4. Summary table
5. Critical and high findings
6. Column-level changes
7. Recommendations

### 5.3 Style guidance
- use clear headings,
- use short bullet points,
- use tables sparingly,
- keep long technical details in HTML where possible.

---

## 6. HTML Report UX Spec

### 6.1 Top-level layout
The HTML report should follow this structure:

1. Hero section
2. Summary cards
3. Severity findings panel
4. Dimensional health panel
5. Column-level diff tables
6. Recommendations section
7. Footer with metadata

### 6.2 Hero section
The hero section should communicate the report result immediately.

Required elements:
- report title: **Schema Sentinel Report**
- compared file names
- overall risk label
- overall score or status badge
- quick recommendation

Preferred layout:
- left: report title and compared files
- right: large overall risk score / badge

### 6.3 Summary cards
The first visible content block under the hero should contain compact cards for:
- Added Columns
- Removed Columns
- Type Changes
- Critical Findings
- High Findings
- Row/Column Count Change

Each card should display:
- short label,
- prominent number,
- optional supporting text.

### 6.4 Dimensional health panel
If dimensional scoring is added, it should not replace the main hero metric.
The recommended layout is:
- keep a large **Overall score** as the main visual anchor,
- place the four dimensions in a side card with compact progress bars.

The four dimensions:
- Completeness
- Uniqueness
- Consistency
- Stability

Why this layout:
- the report stays easy to scan,
- the page keeps a strong hero metric,
- the four bars add depth without making the top section busy.

### 6.5 Findings section
This section should list findings grouped by severity.

Order:
1. Critical
2. High
3. Medium
4. Low

Each finding block should show:
- severity badge,
- title,
- affected column(s),
- short explanation,
- optional recommendation.

### 6.6 Column diff section
This section should be more detailed and table-based.

Recommended columns:
- Column Name
- Status
- Old Type
- New Type
- Old Null %
- New Null %
- Drift Notes
- Severity

### 6.7 Recommendations section
End the report with a short action-oriented section.

Examples:
- Review removed required columns before deploying
- Verify numeric fields that changed to string
- Re-check downstream assumptions for new categories
- Update validation rules if these changes are intentional

---

## 7. Visual Design System

### 7.1 Tone
The visual tone should feel:
- technical but approachable,
- minimal,
- clean,
- modern,
- not overly playful.

### 7.2 Color roles
Recommended semantic color usage:
- Critical: red
- High: orange
- Medium: amber/yellow
- Low: blue or gray
- Success/safe: green

### 7.3 Typography
Use a simple system font stack.
Recommended hierarchy:
- H1: strong and prominent
- H2: clear section titles
- body: readable at normal screen sizes
- code / filenames: monospace

### 7.4 Cards
Cards should have:
- generous whitespace,
- modest border radius,
- soft shadows or light borders,
- consistent padding.

### 7.5 Tables
Tables should:
- be readable,
- avoid dense borders,
- use subtle row striping or hover if convenient,
- support long column names gracefully.

---

## 8. Accessibility Considerations

- Do not rely on color alone for severity
- Use labels like Critical / High / Medium / Low explicitly
- Ensure readable contrast in HTML report
- Avoid tiny text in summary cards
- Keep table labels clear and literal

---

## 9. Error UX

When comparison fails, error messages should be helpful and actionable.

Examples:
- file not found,
- invalid CSV,
- empty file,
- unsupported encoding,
- no comparable columns.

Error messages should say:
- what failed,
- which file is affected,
- and what the user should try next.

Example:

```text
Error: Could not read `new.csv` as a valid CSV file.
Try checking the delimiter, encoding, or file contents.
```

---

## 10. v0.1 Screen Requirements

### Required HTML sections for MVP
- Hero section
- Summary cards
- Findings grouped by severity
- Column changes table
- Recommendations

### Nice-to-have for MVP
- Overall score badge
- Dimensional health split
- Download/export links within local file context

---

## 11. Interaction Model

Schema Sentinel is mostly a static-output experience in v0.1.
No complex browser interaction is required.

Minimal optional interactions in HTML:
- collapsible details for low-severity items,
- anchor links for section navigation,
- hover styles on cards or rows.

These are optional and should not block the MVP.

---

## 12. Design Risks

- too much information above the fold,
- risk scores feeling arbitrary,
- tables becoming cluttered,
- report looking generic instead of distinctive.

Mitigation:
- keep the hero section simple,
- prioritize clarity over decoration,
- group content by severity,
- use short recommendation text.

---

## 13. Final Design Recommendation for MVP

For the first version:
- keep the overall risk/status as the hero metric,
- add dimensional health in a compact side card,
- use severity-grouped findings,
- keep the column diff table detailed but readable,
- make the first screen visually strong enough for README screenshots.

This gives the project both:
- strong usability,
- and strong GitHub presentation value.
