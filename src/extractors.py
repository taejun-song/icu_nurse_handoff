from datetime import datetime, timezone
import pandas as pd
from src.config import SHEET_NAME_TO_PROMPT
from src.schemas import ExtractorOutput, Finding
from src.llm import load_prompt, call_llm, parse_json_response
from src.loader import serialize_dataframe

CHUNK_SIZE = 30


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
        "total_source_rows": len(df),
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
