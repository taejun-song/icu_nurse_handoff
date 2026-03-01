import json
import pandas as pd
from src.schemas import InterpreterOutput, ValidatorOutput
from src.llm import load_prompt, call_llm, parse_json_response
from src.loader import serialize_dataframe


async def validate(
    interpreter_output: InterpreterOutput,
    baseline_sheets: dict[str, pd.DataFrame],
) -> ValidatorOutput:
    system_prompt = load_prompt("validator.md")
    interp_json = json.dumps(interpreter_output.model_dump(), ensure_ascii=False, indent=2)
    baseline_parts = []
    for name, df in baseline_sheets.items():
        if not df.empty:
            baseline_parts.append(serialize_dataframe(df, name))
    baseline_text = "\n\n".join(baseline_parts) if baseline_parts else "No baseline data available."
    user_content = (
        "## Interpreter Output\n"
        f"{interp_json}\n\n"
        "## Baseline Data (Day 1 Context)\n"
        f"{baseline_text}"
    )
    raw = await call_llm(system_prompt, user_content)
    data = parse_json_response(raw)
    data.setdefault("validated_findings", data.get("reconciled_findings", []))
    data.setdefault("missing_findings", [])
    data.setdefault("unresolved_conflicts", [])
    data.setdefault("metadata", {
        "total_validated": len(data["validated_findings"]),
    })
    return ValidatorOutput.model_validate(data)
