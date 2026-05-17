from typing import TypedDict, Literal
from langchain.chat_models.base import init_chat_model
from config.env import OPENAI_API_KEY

ModelName = Literal[
    "grok/gpt-oss-20b",
    "grok/llama-8b",
    "grok/llama-70b",
    "grok/gpt-oss-120b"
]

MODEL_MAP = {
    "grok/llama-8b": "llama-3.1-8b-instant",
    "grok/llama-70b": "llama-3.3-70b-versatile",
    "grok/gpt-oss-20b": "openai/gpt-oss-20b",
    "grok/gpt-oss-120b": "openai/gpt-oss-120b",
}

class FunctionArgs(TypedDict):
    name: ModelName


def get_llm_model(name: ModelName):
    model_id = MODEL_MAP[name]

    return init_chat_model(
        model_provider="groq",
        model=model_id,
        api_key=OPENAI_API_KEY,
        temperature=0.7,
        max_retries=2
    )