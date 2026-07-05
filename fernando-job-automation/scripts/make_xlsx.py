"""
make_xlsx.py — build data/application_tracker.xlsx from the CSV (or empty template).

Adds: styled header, frozen panes, auto column widths, a Status dropdown,
a Scam Risk dropdown, and a small Dashboard sheet with live formulas.

Requires openpyxl:  pip install openpyxl
"""
from __future__ import annotations

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.utils import get_column_letter

from common import TRACKER_COLUMNS, STATUSES, DATA_DIR
from tracker import read_rows

XLSX_PATH = DATA_DIR / "application_tracker.xlsx"
SCAM_LEVELS = ["Low", "Medium", "High", "Reject"]

HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
HEADER_FONT = Font(bold=True, color="FFFFFF", size=11)
TITLE_FONT = Font(bold=True, size=14, color="1F4E78")
THIN = Side(style="thin", color="D9D9D9")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def build() -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Applications"

    # header
    for col, name in enumerate(TRACKER_COLUMNS, start=1):
        c = ws.cell(row=1, column=col, value=name)
        c.fill = HEADER_FILL
        c.font = HEADER_FONT
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = BORDER

    # data rows from CSV
    rows = read_rows()
    for r_idx, row in enumerate(rows, start=2):
        for c_idx, name in enumerate(TRACKER_COLUMNS, start=1):
            cell = ws.cell(row=r_idx, column=c_idx, value=row.get(name, ""))
            cell.border = BORDER
            cell.alignment = Alignment(vertical="top", wrap_text=(name in ("Notes", "Next Action")))

    ws.freeze_panes = "A2"

    # column widths
    widths = {
        "Job Title": 30, "Company": 22, "Location": 20, "Salary": 16,
        "Source": 16, "Application URL": 34, "Contact Name": 16,
        "Contact Email": 24, "Status": 18, "Notes": 44, "Next Action": 26,
        "Remote/Hybrid/On-site": 16,
    }
    for c_idx, name in enumerate(TRACKER_COLUMNS, start=1):
        ws.column_dimensions[get_column_letter(c_idx)].width = widths.get(name, 14)

    # dropdowns (apply to a generous range)
    last = 500
    status_col = get_column_letter(TRACKER_COLUMNS.index("Status") + 1)
    scam_col = get_column_letter(TRACKER_COLUMNS.index("Scam Risk") + 1)

    dv_status = DataValidation(type="list", formula1='"%s"' % ",".join(STATUSES), allow_blank=True)
    dv_status.error = "Pick a value from the list"
    ws.add_data_validation(dv_status)
    dv_status.add(f"{status_col}2:{status_col}{last}")

    dv_scam = DataValidation(type="list", formula1='"%s"' % ",".join(SCAM_LEVELS), allow_blank=True)
    ws.add_data_validation(dv_scam)
    dv_scam.add(f"{scam_col}2:{scam_col}{last}")

    # ------------------------------------------------------------------
    # Dashboard sheet
    # ------------------------------------------------------------------
    dash = wb.create_sheet("Dashboard")
    dash["A1"] = "Fernando — Application Dashboard"
    dash["A1"].font = TITLE_FONT
    dash.column_dimensions["A"].width = 34
    dash.column_dimensions["B"].width = 14

    metrics = [
        ("Total jobs tracked", f'=COUNTA(Applications!C2:C{last})'),
        ("Applied", f'=COUNTIF(Applications!L2:L{last},"Applied")'),
        ("Rejected by Filter", f'=COUNTIF(Applications!L2:L{last},"Rejected by Filter")'),
        ("Saved", f'=COUNTIF(Applications!L2:L{last},"Saved")'),
        ("Interview Requested", f'=COUNTIF(Applications!L2:L{last},"Interview Requested")'),
        ("Interview Completed", f'=COUNTIF(Applications!L2:L{last},"Interview Completed")'),
        ("Offers", f'=COUNTIF(Applications!L2:L{last},"Offer")'),
        ("Follow-Up Sent", f'=COUNTIF(Applications!L2:L{last},"Follow-Up Sent")'),
        ("Avg Fit Score (applied+)", f'=IFERROR(AVERAGEIF(Applications!L2:L{last},"Applied",Applications!M2:M{last}),"-")'),
    ]
    dash["A3"] = "Metric"; dash["B3"] = "Value"
    for cell in ("A3", "B3"):
        dash[cell].fill = HEADER_FILL
        dash[cell].font = HEADER_FONT
    for i, (label, formula) in enumerate(metrics, start=4):
        dash[f"A{i}"] = label
        dash[f"B{i}"] = formula

    dash[f"A{len(metrics)+6}"] = "Statuses cheat sheet:"
    dash[f"A{len(metrics)+6}"].font = Font(bold=True)
    for j, s in enumerate(STATUSES, start=len(metrics) + 7):
        dash[f"A{j}"] = s

    wb.save(XLSX_PATH)
    print(f"Wrote {XLSX_PATH} ({len(rows)} data row(s)).")


if __name__ == "__main__":
    build()
