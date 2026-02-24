import json
from src.schemas import InterpreterOutput, SynthesizerOutput
from src.llm import load_prompt, call_llm, parse_json_response


async def synthesize(interpreter_output: InterpreterOutput) -> SynthesizerOutput:
    system_prompt = load_prompt("synthesizer.md")
    user_content = json.dumps(interpreter_output.model_dump(), ensure_ascii=False, indent=2)
    raw = await call_llm(system_prompt, user_content)
    data = parse_json_response(raw)
    return SynthesizerOutput.model_validate(data)
