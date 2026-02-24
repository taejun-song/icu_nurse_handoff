import re
from datetime import datetime, timezone
import pandas as pd
from src.config import SHEET_NAME_TO_PROMPT
from src.schemas import ExtractorOutput, Finding
from src.llm import load_prompt, call_llm, parse_json_response
from src.loader import serialize_dataframe

CHUNK_SIZE = 60

_NURSING_SKIP = re.compile(
    r"특이\s*사항\s*없음|욕창\s*없음|해당\s*없음|이상\s*없음|변화\s*없음|"
    r"없음\s*$|^-\s*$|^N/?A$",
    re.IGNORECASE,
)

_VITAL_RANGES = {
    "SBP": (90, 180), "DBP": (50, 110), "meanBP": (60, 110),
    "HR": (60, 120), "RR": (8, 30), "BT": (36.0, 38.0), "SpO2": (94, None),
}


def _to_float(val) -> float | None:
    if pd.isna(val):
        return None
    try:
        return float(re.sub(r"[<>≤≥]", "", str(val).strip()).split()[0])
    except (ValueError, IndexError):
        return None


def _parse_ref_range(ref: str) -> tuple[float | None, float | None]:
    if not isinstance(ref, str) or not ref.strip():
        return None, None
    ref = ref.strip()
    m = re.match(r"[<≤]\s*([\d.]+)", ref)
    if m:
        return None, float(m.group(1))
    m = re.match(r"[>≥]\s*([\d.]+)", ref)
    if m:
        return float(m.group(1)), None
    m = re.search(r"([\d.]+)\s*[~\-–—]\s*([\d.]+)", ref)
    if m:
        return float(m.group(1)), float(m.group(2))
    return None, None


def _prefilter(sheet_name: str, df: pd.DataFrame) -> pd.DataFrame:
    original = len(df)
    fn = _PREFILTERS.get(sheet_name)
    if fn is None:
        return df
    filtered = fn(df)
    removed = original - len(filtered)
    if removed > 0:
        print(f"    pre-filter: {original} → {len(filtered)} rows (-{removed})")
    return filtered


def _prefilter_lab(df: pd.DataFrame) -> pd.DataFrame:
    if not {"Result", "Reference Range"}.issubset(df.columns):
        return df
    keep = []
    for _, row in df.iterrows():
        num = _to_float(row["Result"])
        if num is None:
            keep.append(True)
            continue
        lo, hi = _parse_ref_range(str(row.get("Reference Range", "")))
        if lo is None and hi is None:
            keep.append(True)
            continue
        outside = (lo is not None and num < lo) or (hi is not None and num > hi)
        keep.append(outside)
    return df[keep].copy()


def _prefilter_nursing(df: pd.DataFrame) -> pd.DataFrame:
    if "Nursing Note" not in df.columns:
        return df
    mask = df["Nursing Note"].apply(
        lambda x: pd.notna(x) and str(x).strip() != "" and not _NURSING_SKIP.search(str(x).strip())
    )
    return df[mask].copy()


def _prefilter_medication(df: pd.DataFrame) -> pd.DataFrame:
    if "Datetime" not in df.columns or "Order" not in df.columns:
        return df
    return df.drop_duplicates(subset=["Datetime", "Order"], keep="first").copy()


def _prefilter_procedure(df: pd.DataFrame) -> pd.DataFrame:
    if "Datetime" not in df.columns or "Order" not in df.columns:
        return df
    return df.drop_duplicates(subset=["Datetime", "Order"], keep="first").copy()


def _prefilter_flowsheet(df: pd.DataFrame) -> pd.DataFrame:
    vital_cols = [c for c in _VITAL_RANGES if c in df.columns]
    has_memo = "Memo" in df.columns
    keep = []
    for _, row in df.iterrows():
        if has_memo and pd.notna(row.get("Memo")) and str(row["Memo"]).strip():
            keep.append(True)
            continue
        abnormal = False
        for col in vital_cols:
            num = _to_float(row.get(col))
            if num is None:
                continue
            lo, hi = _VITAL_RANGES[col]
            if (lo is not None and num < lo) or (hi is not None and num > hi):
                abnormal = True
                break
        keep.append(abnormal)
    return df[keep].copy()


_PREFILTERS = {
    "Laboratory Test Results": _prefilter_lab,
    "Nursing Notes": _prefilter_nursing,
    "Medication Orders": _prefilter_medication,
    "Procedure Orders": _prefilter_procedure,
    "Flowsheet": _prefilter_flowsheet,
}


async def _extract_chunk(sheet_name: str, df: pd.DataFrame, system_prompt: str) -> list[dict]:
    user_content = serialize_dataframe(df, sheet_name)
    raw = await call_llm(system_prompt, user_content)
    try:
        data = parse_json_response(raw)
    except Exception as e:
        print(f"    [WARN] chunk parse failed ({e}), skipping")
        return []
    return data.get("findings", [])


async def extract_sheet(sheet_name: str, df: pd.DataFrame) -> ExtractorOutput:
    total_rows = len(df)
    df = _prefilter(sheet_name, df)
    prompt_file = SHEET_NAME_TO_PROMPT[sheet_name]
    system_prompt = load_prompt(prompt_file)
    if len(df) <= CHUNK_SIZE:
        user_content = serialize_dataframe(df, sheet_name)
        raw = await call_llm(system_prompt, user_content)
        try:
            data = parse_json_response(raw)
        except Exception as e:
            print(f"  [WARN] {sheet_name}: JSON parse failed ({e}), returning empty findings")
            data = {"findings": []}
    else:
        all_findings = []
        chunks = [df.iloc[i:i + CHUNK_SIZE] for i in range(0, len(df), CHUNK_SIZE)]
        for j, chunk_df in enumerate(chunks, 1):
            print(f"    chunk {j}/{len(chunks)} ({len(chunk_df)} rows)...")
            findings = await _extract_chunk(sheet_name, chunk_df, system_prompt)
            all_findings.extend(findings)
            print(f"    chunk {j}/{len(chunks)} → {len(findings)} findings")
        data = {"findings": all_findings}
    data["sheet_name"] = sheet_name
    data["extraction_datetime"] = datetime.now(timezone.utc).isoformat()
    data.setdefault("metadata", {
        "total_source_rows": total_rows,
        "findings_extracted": len(data["findings"]),
        "date_range": "N/A",
    })
    return ExtractorOutput.model_validate(data)


async def extract_all(data_sheets: dict[str, pd.DataFrame]) -> list[ExtractorOutput]:
    results = []
    sheets = [(n, df) for n, df in data_sheets.items() if not df.empty and n in SHEET_NAME_TO_PROMPT]
    for i, (name, df) in enumerate(sheets, 1):
        print(f"  [{i}/{len(sheets)}] Extracting: {name} ({len(df)} rows)...")
        result = await extract_sheet(name, df)
        print(f"  [{i}/{len(sheets)}] Done: {name} → {len(result.findings)} findings")
        results.append(result)
    return results
