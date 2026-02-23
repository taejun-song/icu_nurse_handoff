import asyncio
from datetime import datetime, timezone
import pandas as pd
from src.config import SHEET_NAME_TO_PROMPT
from src.schemas import ExtractorOutput
from src.llm import load_prompt, call_llm, parse_json_response
from src.loader import serialize_dataframe


async def extract_sheet(sheet_name: str, df: pd.DataFrame) -> ExtractorOutput:
    prompt_file = SHEET_NAME_TO_PROMPT[sheet_name]
    system_prompt = load_prompt(prompt_file)
    user_content = serialize_dataframe(df, sheet_name)
    raw = await call_llm(system_prompt, user_content)
    data = parse_json_response(raw)
    data["sheet_name"] = sheet_name
    data["extraction_datetime"] = datetime.now(timezone.utc).isoformat()
    return ExtractorOutput.model_validate(data)


async def extract_all(data_sheets: dict[str, pd.DataFrame]) -> list[ExtractorOutput]:
    tasks = []
    for name, df in data_sheets.items():
        if df.empty:
            continue
        if name not in SHEET_NAME_TO_PROMPT:
            continue
        tasks.append(extract_sheet(name, df))
    return await asyncio.gather(*tasks)
