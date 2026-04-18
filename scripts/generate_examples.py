from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "examples"
OLD_PATH = OUTPUT_DIR / "old.csv"
NEW_PATH = OUTPUT_DIR / "new.csv"
OLD_ROWS = 1000
NEW_ROWS = 1100

PAYMENT_METHODS = (
    "Electronic check",
    "Mailed check",
    "Bank transfer (automatic)",
    "Credit card (automatic)",
)

FEEDBACK_SNIPPETS = (
    "Support was responsive and the package feels fair",
    "The service works well but the price feels high",
    "Setup was easy and the app is straightforward",
    "The connection is stable and billing is clear",
    "I would keep the plan if the monthly fee was lower",
)


def customer_id(index: int) -> str:
    return f"CUST-{index:06d}"


def cycle_value(values: tuple[str, ...], index: int) -> str:
    return values[index % len(values)]


def build_record(index: int, *, include_backup: bool, include_feedback: bool) -> dict[str, str]:
    gender = cycle_value(("Female", "Male"), index)
    senior = "1" if index % 8 in (0, 1) else "0"
    partner = "Yes" if index % 3 in (0, 1) else "No"
    dependents = "Yes" if index % 5 in (0, 1) else "No"
    tenure = 1 + (index * 7) % 72
    phone_service = "No" if index % 11 == 0 else "Yes"
    if phone_service == "No":
        multiple_lines = "No phone service"
    else:
        multiple_lines = "Yes" if index % 4 in (0, 1) else "No"

    internet_service = cycle_value(("DSL", "Fiber optic", "No"), index)
    if include_backup:
        if internet_service == "No":
            online_backup = "No internet service"
        else:
            online_backup = "Yes" if index % 3 != 0 else "No"

    contract = cycle_value(("Month-to-month", "One year", "Two year"), index)
    paperless = "Yes" if contract == "Month-to-month" or index % 2 == 0 else "No"

    if include_feedback and index % 17 == 0:
        payment_method = "Digital wallet"
    else:
        payment_method = cycle_value(PAYMENT_METHODS, index)

    internet_base = {"DSL": 44.0, "Fiber optic": 79.0, "No": 22.0}[internet_service]
    monthly_old = round(
        internet_base
        + {"Month-to-month": 12.0, "One year": 4.5, "Two year": -1.5}[contract]
        + (7.0 if multiple_lines == "Yes" else -1.5 if multiple_lines == "No" else 0.0)
        + (index % 6) * 0.75,
        2,
    )

    if include_feedback:
        monthly_charges = round(
            monthly_old
            + (25.0 if internet_service == "Fiber optic" else 18.0 if internet_service == "DSL" else 8.0),
            2,
        )
    else:
        monthly_charges = monthly_old

    total_charges = round(
        tenure * (internet_base + {"Month-to-month": 3.0, "One year": 1.0, "Two year": -0.5}[contract])
        + (index % 4) * 2.5,
        2,
    )

    churn_score = 0
    if contract == "Month-to-month":
        churn_score += 2
    if monthly_charges >= 95:
        churn_score += 1
    if senior == "1":
        churn_score += 1
    if internet_service == "Fiber optic":
        churn_score += 1
    churn = "Yes" if churn_score >= 3 else "No"

    row = {
        "customerID": customer_id(index),
        "gender": gender,
        "SeniorCitizen": senior,
        "Partner": partner,
        "Dependents": dependents,
        "tenure": str(tenure),
        "PhoneService": phone_service,
        "MultipleLines": multiple_lines,
        "InternetService": internet_service,
        "Contract": contract,
        "PaperlessBilling": paperless,
        "PaymentMethod": payment_method,
        "MonthlyCharges": f"{monthly_charges:.2f}",
        "TotalCharges": f"{total_charges:.2f}",
        "Churn": churn,
    }

    if include_backup:
        row["OnlineBackup"] = online_backup

    if include_feedback:
        snippet = FEEDBACK_SNIPPETS[index % len(FEEDBACK_SNIPPETS)]
        if churn == "Yes":
            feedback = f"{snippet}; likely to cancel without a better offer"
        elif payment_method == "Digital wallet":
            feedback = f"{snippet}; new payment option is convenient"
        else:
            feedback = f"{snippet}; no major issues this month"
        row["CustomerFeedback"] = feedback

    return row


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    old_rows = [build_record(index, include_backup=True, include_feedback=False) for index in range(OLD_ROWS)]
    new_rows = [build_record(index, include_backup=False, include_feedback=True) for index in range(OLD_ROWS)]
    new_rows.extend(
        build_record(index, include_backup=False, include_feedback=True)
        for index in range(OLD_ROWS, NEW_ROWS)
    )

    old_fields = [
        "customerID",
        "gender",
        "SeniorCitizen",
        "Partner",
        "Dependents",
        "tenure",
        "PhoneService",
        "MultipleLines",
        "InternetService",
        "OnlineBackup",
        "Contract",
        "PaperlessBilling",
        "PaymentMethod",
        "MonthlyCharges",
        "TotalCharges",
        "Churn",
    ]
    new_fields = [
        "customerID",
        "gender",
        "SeniorCitizen",
        "Partner",
        "Dependents",
        "tenure",
        "PhoneService",
        "MultipleLines",
        "InternetService",
        "Contract",
        "PaperlessBilling",
        "PaymentMethod",
        "MonthlyCharges",
        "TotalCharges",
        "Churn",
        "CustomerFeedback",
    ]

    write_csv(OLD_PATH, old_rows, old_fields)
    write_csv(NEW_PATH, new_rows, new_fields)


if __name__ == "__main__":
    main()
