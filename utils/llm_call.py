from langchain.chat_models.base import init_chat_model
from config.env import OPENAI_API_KEY



def get_llm_model():
    model = init_chat_model(model_provider='groq', model='llama-3.3-70b-versatile', api_key=OPENAI_API_KEY, max_retries=2)
    return model