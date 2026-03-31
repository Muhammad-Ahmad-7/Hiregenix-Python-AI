from langchain_google_genai import GoogleGenerativeAIEmbeddings
from config.env import OPENAI_API_KEY

from langchain_huggingface import HuggingFaceEndpointEmbeddings

def get_huggingface_embedding(text: str):
    """
    Generate free embeddings using HuggingFace's hosted Inference API.
    Does NOT require local PyTorch.
    """
    model = HuggingFaceEndpointEmbeddings(
        model="sentence-transformers/all-MiniLM-L6-v2",
        huggingfacehub_api_token="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",
    )
    return model.embed_query(text)


def get_gemini_embedding(text: str):
    """Generate text embeddings using Gemini's smaller embedding model."""
    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/embedding-001",
        google_api_key=OPENAI_API_KEY
    )
    return embeddings.embed_query(text=text)
