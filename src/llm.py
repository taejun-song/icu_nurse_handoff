import hashlib
import json
import anthropic
from pathlib import Path
from src.config import LLM_MODEL, LLM_TEMPERATURE, LLM_MAX_TOKENS, PROMPTS_DIR, CACHE_DIR


def load_prompt(filename: str) -> str:
    path = PROMPTS_DIR / filename
    return path.read_text(encoding="utf-8").strip()


def _cache_key(system_prompt: str, user_content: str) -> str:
    combined = f"{system_prompt}\n---\n{user_content}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


async def call_llm(system_prompt: str, user_content: str) -> str:
    cache_hash = _cache_key(system_prompt, user_content)
    cache_file = CACHE_DIR / f"{cache_hash}.json"
    if cache_file.exists():
        cached = json.loads(cache_file.read_text(encoding="utf-8"))
        return cached["response"]
    client = anthropic.AsyncAnthropic()
    response = await client.messages.create(
        model=LLM_MODEL,
        temperature=LLM_TEMPERATURE,
        max_tokens=LLM_MAX_TOKENS,
        system=system_prompt,
        messages=[{"role": "user", "content": user_content}],
    )
    text = response.content[0].text
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps({"response": text}, ensure_ascii=False), encoding="utf-8")
    return text


def parse_json_response(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        start = 1
        end = len(lines) - 1
        if lines[0].startswith("```json"):
            start = 1
        for i in range(len(lines) - 1, 0, -1):
            if lines[i].strip() == "```":
                end = i
                break
        text = "\n".join(lines[start:end])
    return json.loads(text)
