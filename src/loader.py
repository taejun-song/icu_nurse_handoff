import re
import pandas as pd
from pathlib import Path
from src.config import SHEET_NAMES

EXPECTED_COLUMNS = {
    "Physician Notes": ["Datetime", "Type", "Finding", "Assessment", "Plan", "Consultation"],
    "Nursing Notes": ["Datetime", "Nursing Note"],
    "Imaging Results": ["Datetime", "Type", "Conclusion", "Finding", "Clinical Information"],
    "Laboratory Test Results": ["Datetime", "Test", "Specimen", "Test Item", "Result", "Reference Range"],
    "Medication Orders": ["Datetime", "Type", "Order", "Comment"],
    "Procedure Orders": ["Datetime", "Type", "Order", "Comment"],
    "Flowsheet": ["Datetime", "SBP", "DBP", "meanBP", "HR", "RR", "BT", "SpO2", "EKG", "Memo"],
    "Nursing Risk Assessment": ["Datetime", "Nursing Risk Asssessment", "Item", "Result", "Score"],
}

_DT_PATTERN = re.compile(r"\((\d{4}-\d{2}-\d{2}[\s\d:]*)\)")


def _normalize_datetime(val: str | None) -> str | None:
    if not isinstance(val, str):
        return None
    m = _DT_PATTERN.search(val)
    if not m:
        return val.strip()
    raw = m.group(1).strip()
    try:
        dt = pd.to_datetime(raw)
        return dt.isoformat()
    except Exception:
        return raw


def load_emr_file(path: str | Path) -> dict[str, pd.DataFrame]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"EMR file not found: {path}")
    all_sheets = pd.read_excel(path, engine="openpyxl", sheet_name=None)
    result: dict[str, pd.DataFrame] = {}
    for name in SHEET_NAMES:
        if name not in all_sheets:
            print(f"[WARN] Sheet '{name}' not found in {path.name}")
            result[name] = pd.DataFrame()
            continue
        df = all_sheets[name]
        if df.empty:
            print(f"[WARN] Sheet '{name}' is empty in {path.name}")
            result[name] = df
            continue
        try:
            expected = EXPECTED_COLUMNS.get(name, [])
            actual = list(df.columns)
            missing = [c for c in expected if c not in actual]
            if missing:
                print(f"[WARN] Sheet '{name}' missing columns: {missing}")
            if "Datetime" in df.columns:
                df["Datetime"] = df["Datetime"].apply(_normalize_datetime)
            if name == "Laboratory Test Results" and "Result" in df.columns:
                df["Result"] = df["Result"].astype(str)
            result[name] = df
        except Exception as e:
            print(f"[ERROR] Sheet '{name}' processing failed: {e}")
            result[name] = pd.DataFrame()
    return result


def load_baseline_safe(path: str | Path) -> dict[str, pd.DataFrame]:
    path = Path(path)
    if not path.exists():
        print(f"[WARN] Baseline file not found: {path}. Skipping baseline context.")
        return {name: pd.DataFrame() for name in SHEET_NAMES}
    return load_emr_file(path)


def serialize_dataframe(df: pd.DataFrame, sheet_name: str) -> str:
    if df.empty:
        return f"[{sheet_name}]: No data available."
    serializers = {
        "Flowsheet": serialize_flowsheet,
        "Laboratory Test Results": serialize_lab_results,
        "Nursing Risk Assessment": serialize_risk_assessment,
    }
    if sheet_name in serializers:
        return serializers[sheet_name](df)
    return f"[{sheet_name}] ({len(df)} rows)\n{df.to_csv(index=False)}"


def serialize_flowsheet(df: pd.DataFrame) -> str:
    vital_cols = ["Datetime", "SBP", "DBP", "meanBP", "HR", "RR", "BT", "SpO2"]
    parts = ["[Flowsheet — Vital Signs]"]
    existing_vital_cols = [c for c in vital_cols if c in df.columns]
    vitals = df[existing_vital_cols].dropna(how="all", subset=[c for c in existing_vital_cols if c != "Datetime"])
    if not vitals.empty:
        parts.append(f"({len(vitals)} rows)")
        parts.append(vitals.to_csv(index=False))
    else:
        parts.append("No vital sign data.")
    parts.append("\n[Flowsheet — Memo]")
    if "Memo" in df.columns:
        memo_rows = df[df["Memo"].notna() & (df["Memo"].astype(str).str.strip() != "")]
        if not memo_rows.empty:
            for _, row in memo_rows.iterrows():
                dt = row.get("Datetime", "")
                parts.append(f"- [{dt}] {row['Memo']}")
        else:
            parts.append("No memo entries.")
    else:
        parts.append("No Memo column.")
    return "\n".join(parts)


def serialize_lab_results(df: pd.DataFrame) -> str:
    parts = ["[Laboratory Test Results]"]
    if "Test Item" not in df.columns:
        return f"[Laboratory Test Results] ({len(df)} rows)\n{df.to_csv(index=False)}"
    for item, group in df.groupby("Test Item", sort=False):
        ref = group["Reference Range"].dropna().unique() if "Reference Range" in group.columns else []
        ref_str = f" (Ref: {ref[0]})" if len(ref) > 0 else ""
        parts.append(f"\n### {item}{ref_str}")
        display_cols = [c for c in ["Datetime", "Result"] if c in group.columns]
        parts.append(group[display_cols].to_csv(index=False))
    return "\n".join(parts)


def serialize_risk_assessment(df: pd.DataFrame) -> str:
    parts = ["[Nursing Risk Assessment]"]
    if "Datetime" not in df.columns:
        return f"[Nursing Risk Assessment] ({len(df)} rows)\n{df.to_csv(index=False)}"
    for dt, group in df.groupby("Datetime", sort=False):
        parts.append(f"\n### {dt}")
        total_rows = group[group["Item"].isna() | (group["Item"].astype(str).str.strip() == "")]
        if not total_rows.empty and "Score" in total_rows.columns:
            parts.append(f"Total Score: {total_rows['Score'].iloc[0]}")
        item_rows = group[group["Item"].notna() & (group["Item"].astype(str).str.strip() != "")]
        if not item_rows.empty:
            display_cols = [c for c in ["Item", "Result", "Score"] if c in item_rows.columns]
            parts.append(item_rows[display_cols].to_csv(index=False))
    return "\n".join(parts)
