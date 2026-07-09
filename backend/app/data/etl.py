import calendar
import os
import re
from datetime import datetime

import polars as pl

from app.config.constants import COL_AR_PERSON, COL_SALES_CODE
from app.config.settings import IMPORT_DIR, MAPPING_DIR
from app.data.db import load_data
from app.models.schema import clean_columns, validate_mapping

NUMERIC_COLUMNS = [
    "bal_due",
    "total_amt_overdue",
    "cr_limit",
    "0_-_6",
    "7_-_13",
    "14_-_20",
    "21_-_29",
    "30_-_37",
    "30_-_38",
    "38_-_45",
    "45_up",
    "60_up",
]
DATE_LIKE_PATTERN = re.compile(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}.*")

# Khi Excel tự động chuyển "7 - 13" thành ngày (July 13), cột này sẽ có tên
# dạng date hoặc số serial Excel. Ta dùng vị trí tương đối so với cột neo
# "0 - 6" (hoặc "0_-_6") để nhận diện và đặt lại tên chuẩn.
# offset -> tên cột chuẩn sau khi clean
AGING_OFFSET_MAP = {
    0: "0_-_6",
    1: "7_-_13",    # hay bị Excel convert thành date
    2: "14_-_20",
    3: "21_-_29",
    4: "30_-_37",
    5: "38_-_45",
    6: "45_up",
    7: "60_up",
}


def read_excel_sheet(filepath: str, has_header: bool = False) -> pl.DataFrame:
    sheet_names = []
    try:
        sheet_names = pl.read_excel(filepath, sheet_id=0, read_csv_options={"has_header": False}).columns
    except Exception:
        pass

    try:
        workbook = pl.read_excel(filepath, sheet_id=None)
        if isinstance(workbook, dict):
            sheet_names = list(workbook.keys())
        elif isinstance(workbook, list):
            sheet_names = [str(i) for i in range(len(workbook))]
    except Exception:
        pass

    candidates = ["Raw data", "Sheet1", "sheet1", "Data", "data", "raw", *sheet_names]
    for sheet_name in candidates:
        if not sheet_name:
            continue
        try:
            return pl.read_excel(filepath, sheet_name=sheet_name, has_header=has_header)
        except Exception:
            continue

    try:
        return pl.read_excel(filepath, sheet_id=0, has_header=has_header)
    except Exception as exc:
        raise RuntimeError(f"Unable to read Excel workbook: {exc}") from exc


def extract_headers(df: pl.DataFrame) -> pl.DataFrame:
    header_row_index = 0
    for index in range(min(10, df.shape[0])):
        row_values = [str(value).lower() for value in df.row(index) if value is not None]
        if any("cust" in value or "sales person" in value for value in row_values):
            header_row_index = index
            break

    headers = list(df.row(header_row_index))
    new_headers = []
    seen = {}
    for index, header in enumerate(headers):
        value = str(header) if header is not None and str(header).strip() != "" else f"unnamed_{index}"
        value = value.replace("\n", " ").strip()

        if value in seen:
            seen[value] += 1
            value = f"{value}_{seen[value]}"
        else:
            seen[value] = 0

        new_headers.append(value)

    df = df.slice(header_row_index + 1)
    df.columns = new_headers
    return df


def normalize_mapping_columns(mapping_df: pl.DataFrame) -> pl.DataFrame:
    if COL_AR_PERSON in mapping_df.columns:
        return mapping_df

    for candidate in [COL_AR_PERSON, "ar", "assigned_ar_person", "owner"]:
        if candidate in mapping_df.columns:
            return mapping_df.rename({candidate: COL_AR_PERSON})

    return mapping_df


def _heal_date_corrupted_columns(df: pl.DataFrame) -> pl.DataFrame:
    """Dùng vị trí tương đối để phục hồi các cột bị Excel tự chuyển thành
    ngày/số serial (ví dụ: '7 - 13' -> 2026-07-13 hoặc 46216).
    Cột neo: '0_-_6' (không bao giờ bị Excel convert).
    """
    cols = df.columns
    # Tìm cột neo '0_-_6'
    anchor_idx = None
    for i, c in enumerate(cols):
        c_clean = str(c).strip().lower().replace(" ", "_").replace("-", "-")
        if c_clean in ("0_-_6", "0_6", "0 - 6"):
            anchor_idx = i
            break
    if anchor_idx is None:
        return df

    rename_pairs = {}
    for offset, canonical in AGING_OFFSET_MAP.items():
        col_idx = anchor_idx + offset
        if col_idx >= len(cols):
            break
        col_name = str(cols[col_idx])
        # Nếu tên cột trông như ngày (yyyy-mm-dd), số Excel serial, hoặc
        # không khớp tên chuẩn -> đặt lại theo vị trí
        is_date_like = bool(DATE_LIKE_PATTERN.match(col_name))
        is_serial = re.match(r"^\d{5}$", col_name)  # Excel serial 5 chữ số
        already_correct = col_name == canonical
        if (is_date_like or is_serial) and not already_correct:
            rename_pairs[col_name] = canonical

    for old, new in rename_pairs.items():
        df = df.rename({old: new})
    return df


def standardize_columns(df: pl.DataFrame) -> pl.DataFrame:
    df = clean_columns(df)

    rename_map = {
        "cust_id": "cust_id",
        "cust_#": "cust_id",
        "name": "name",
        "sales_person_code": "sales_person_code",
        "term": "term",
        "0_-_6": "0_-_6",
        "7_-_13": "7_-_13",
        "14_-_20": "14_-_20",
        "21_-_29": "21_-_29",
        "30_-_37": "30_-_37",
        "30_-_38": "30_-_38",
        "38_-_45": "38_-_45",
        "45_up": "45_up",
        "60_up": "60_up",
        "bal_due": "bal_due",
        "balance_due": "bal_due",
        "total_amt": "total_amt_overdue",
        "total_amt_overdue": "total_amt_overdue",
        "cr_limit": "cr_limit",
        "credit_limit": "cr_limit",
    }

    for column in list(df.columns):
        if column in rename_map:
            df = df.rename({column: rename_map[column]})

    # Phục hồi các cột bị Excel tự convert thành date (ví dụ: 7-13 -> July 13)
    df = _heal_date_corrupted_columns(df)

    # Loại bỏ các cột còn lại có tên dạng ngày (cột rác)
    keep_columns = [c for c in df.columns if not DATE_LIKE_PATTERN.match(str(c))]
    if len(keep_columns) != len(df.columns):
        df = df.select(keep_columns)

    return df


def get_snapshot_info(filename: str) -> tuple:
    month_match = re.search(r"MONTH_(\d+)", filename, re.IGNORECASE)
    day_match = re.search(r"DAY_(\d+)", filename, re.IGNORECASE)
    month = int(month_match.group(1)) if month_match else datetime.now().month
    year = 2026

    if day_match:
        day = int(day_match.group(1))
        return "daily", datetime(year, month, day, 12, 0, 0)

    last_day = calendar.monthrange(year, month)[1]
    return "monthly", datetime(year, month, last_day, 23, 59, 59)


def _load_mapping_df() -> pl.DataFrame:
    mapping_candidates = [MAPPING_DIR / "assign_ar_team.xlsx", MAPPING_DIR / "assign_ar_team.csv"]
    for path in mapping_candidates:
        if not path.exists():
            continue
        if path.suffix.lower() == ".xlsx":
            mapping_df = read_excel_sheet(str(path), has_header=False)
        else:
            mapping_df = pl.read_csv(str(path), has_header=False)

        mapping_df = extract_headers(mapping_df)
        mapping_df = standardize_columns(mapping_df)
        mapping_df = normalize_mapping_columns(mapping_df)
        return mapping_df.unique(subset=[COL_SALES_CODE], maintain_order=True)

    return pl.DataFrame(
        {COL_SALES_CODE: [], COL_AR_PERSON: []},
        schema={COL_SALES_CODE: pl.Utf8, COL_AR_PERSON: pl.Utf8},
    )


def process_file(filepath: str) -> dict:
    try:
        if filepath.lower().endswith(".csv"):
            raw_df = pl.read_csv(filepath)
            raw_df = clean_columns(raw_df)
        else:
            raw_df = read_excel_sheet(filepath, has_header=False)
            raw_df = extract_headers(raw_df)
            raw_df = standardize_columns(raw_df)

        mapping_df = _load_mapping_df()
        validation = validate_mapping(raw_df, mapping_df)
        enriched_df = raw_df.join(mapping_df, on=COL_SALES_CODE, how="left")

        for column in NUMERIC_COLUMNS:
            if column in enriched_df.columns:
                enriched_df = enriched_df.with_columns(pl.col(column).cast(pl.Float64, strict=False))

        enriched_df = enriched_df.with_columns(pl.col(COL_AR_PERSON).fill_null("Unassigned"))

        file_name = os.path.basename(filepath)
        snapshot_type, imported_at = get_snapshot_info(file_name)
        load_data(raw_df, enriched_df, file_name, snapshot_type=snapshot_type, custom_imported_at=imported_at)

        return {
            "success": True,
            "message": "Data processed successfully.",
            "missing_codes": validation["missing_codes"],
        }
    except Exception as exc:
        return {
            "success": False,
            "message": f"Error processing excel: {exc}",
            "missing_codes": [],
        }
