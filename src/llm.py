import hashlib
import json
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from src.config import LLM_MODEL, LLM_TEMPERATURE, LLM_MAX_TOKENS, PROMPTS_DIR, CACHE_DIR

_tokenizer = None
_model = None


def _load_model():
    global _tokenizer, _model
    if _model is None:
        _tokenizer = AutoTokenizer.from_pretrained(LLM_MODEL)
        if _tokenizer.pad_token is None:
            _tokenizer.pad_token = _tokenizer.eos_token
        _model = AutoModelForCausalLM.from_pretrained(
            LLM_MODEL, torch_dtype=torch.bfloat16, device_map="auto",
        )
    return _tokenizer, _model


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
    tokenizer, model = _load_model()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]
    text_input = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True,
    )
    encoded = tokenizer(text_input, return_tensors="pt").to(model.device)
    gen_kwargs = {
        "max_new_tokens": LLM_MAX_TOKENS,
        "pad_token_id": tokenizer.pad_token_id,
    }
    if LLM_TEMPERATURE > 0:
        gen_kwargs["do_sample"] = True
        gen_kwargs["temperature"] = LLM_TEMPERATURE
    else:
        gen_kwargs["do_sample"] = False
    output_ids = model.generate(**encoded, **gen_kwargs)
    new_tokens = output_ids[0][encoded["input_ids"].shape[-1]:]
    text = tokenizer.decode(new_tokens, skip_special_tokens=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps({"response": text}, ensure_ascii=False), encoding="utf-8")
    return text


def _repair_truncated_json(text: str) -> str:
    open_braces = 0
    open_brackets = 0
    in_string = False
    escape = False
    last_valid = 0
    for i, ch in enumerate(text):
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            open_braces += 1
        elif ch == "}":
            open_braces -= 1
        elif ch == "[":
            open_brackets += 1
        elif ch == "]":
            open_brackets -= 1
        if open_braces == 0 and open_brackets == 0:
            last_valid = i + 1
            break
    if last_valid > 0:
        return text[:last_valid]
    text = text.rstrip().rstrip(",")
    text += "]}" * 0 + "]" * open_brackets + "}" * open_braces
    return text


def parse_json_response(text: str) -> dict:
    import re
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*\n(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    if not text.startswith("{") and not text.startswith("["):
        match = re.search(r"(\{.*)", text, re.DOTALL)
        if match:
            text = match.group(1)
    text = _repair_truncated_json(text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        text = re.sub(r',\s*([}\]])', r'\1', text)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            print(f"[LLM] Failed to parse JSON. Raw output:\n{text[:500]}")
            raise
