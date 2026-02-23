import json
import pandas as pd
from src.config import OUTPUT_FRAMEWORK
from src.schemas import InterpreterOutput, SynthesizerOutput
from src.llm import load_prompt, call_llm, parse_json_response


def _load_output_framework() -> str:
    df = pd.DataFrame(OUTPUT_FRAMEWORK)
    df.columns = ["Level 1", "Level 2", "Level 3"]
    return f"\n\n## Output Framework\n{df.to_csv(index=False)}"


async def synthesize(interpreter_output: InterpreterOutput) -> SynthesizerOutput:
    system_prompt = load_prompt("synthesizer.md") + _load_output_framework()
    user_content = json.dumps(interpreter_output.model_dump(), ensure_ascii=False, indent=2)
    raw = await call_llm(system_prompt, user_content)
    data = parse_json_response(raw)
    return SynthesizerOutput.model_validate(data)
