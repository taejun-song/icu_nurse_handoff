import json
import pandas as pd
from src.schemas import ExtractorOutput, InterpreterOutput
from src.llm import load_prompt, call_llm, parse_json_response
from src.loader import serialize_dataframe


async def interpret(
    extractor_outputs: list[ExtractorOutput],
    baseline_sheets: dict[str, pd.DataFrame],
) -> InterpreterOutput:
    system_prompt = load_prompt("interpreter.md")
    extractions_json = json.dumps(
        [eo.model_dump() for eo in extractor_outputs], ensure_ascii=False, indent=2
    )
    baseline_parts = []
    for name, df in baseline_sheets.items():
        if not df.empty:
            baseline_parts.append(serialize_dataframe(df, name))
    baseline_text = "\n\n".join(baseline_parts) if baseline_parts else "No baseline data available."
    user_content = (
        "## Extractor Outputs\n"
        f"{extractions_json}\n\n"
        "## Baseline Data (Day 1 Context)\n"
        f"{baseline_text}"
    )
    raw = await call_llm(system_prompt, user_content)
    data = parse_json_response(raw)
    return InterpreterOutput.model_validate(data)
