from typing import TypedDict
from langchain.chat_models.base import init_chat_model
from config.env import OPENAI_API_KEY, GROK_API_KEY, GEMINI_API_KEY

GROK_MODEL_MAP = {
    "grok/llama-8b": "llama-3.1-8b-instant",
    "grok/llama-70b": "llama-3.3-70b-versatile",
    "grok/gpt-oss-20b": "openai/gpt-oss-20b",
    "grok/gpt-oss-120b": "openai/gpt-oss-120b",
}

OPENAI_MODEL_MAP = {
    "openai/gpt-4o-mini": "gpt-4o-mini",
    "openai/gpt-4.1-mini": "gpt-4.1-mini",
}

GEMINI_MODEL_MAP = {
    "gemini/gemini-1.5-flash": "gemini-1.5-flash-002",
    "gemini/gemini-1.5-flash-002": "gemini-1.5-flash-002",
    "gemini/gemini-2.5-flash": "gemini-2.5-flash"
}

class FunctionArgs(TypedDict):
    name: str


def get_llm_model(name: str):
    provider, model_name = name.split("/", 1)

    if provider == "grok":
        model_id = GROK_MODEL_MAP.get(name)
        if not model_id:
            raise ValueError(f"Unknown Grok model: {name}")
        return init_chat_model(
            model_provider="groq",
            model=model_id,
            api_key=GROK_API_KEY,
            temperature=0.7,
            max_retries=2
        )

    if provider == "openai":
        model_id = OPENAI_MODEL_MAP.get(name)
        if not model_id:
            raise ValueError(f"Unknown OpenAI model: {name}")
        return init_chat_model(
            model_provider="openai",
            model=model_id,
            api_key=OPENAI_API_KEY,
            temperature=0.7,
            max_retries=2
        )

    if provider == "gemini":
        model_id = GEMINI_MODEL_MAP.get(name)
        if not model_id:
            raise ValueError(f"Unknown Gemini model: {name}")
        return init_chat_model(
            model_provider="google_genai",
            model=model_id,
            api_key=GEMINI_API_KEY,
            temperature=0.7,
            max_retries=2
        )

    raise ValueError(f"Unsupported model provider: {provider}")