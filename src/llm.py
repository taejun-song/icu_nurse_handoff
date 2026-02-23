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
