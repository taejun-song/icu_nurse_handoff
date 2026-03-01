import json
from src.schemas import ValidatorOutput, GeneratorOutput
from src.llm import load_prompt, call_llm, parse_json_response


async def generate(validator_output: ValidatorOutput) -> GeneratorOutput:
    system_prompt = load_prompt("generator.md")
    user_content = json.dumps(validator_output.model_dump(), ensure_ascii=False, indent=2)
    raw = await call_llm(system_prompt, user_content)
    data = parse_json_response(raw)
    data.setdefault("summary", "")
    data.setdefault("metadata", {
        "total_findings_used": len(validator_output.validated_findings),
    })
    return GeneratorOutput.model_validate(data)
