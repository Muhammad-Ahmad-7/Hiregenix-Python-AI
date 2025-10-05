from langchain_google_genai import GoogleGenerativeAIEmbeddings
from config.env import OPENAI_API_KEY
from langchain_huggingface import HuggingFaceEmbeddings


def get_gemini_embedding(text: str):
    """Generate text embeddings using Gemini's smaller embedding model."""
    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/embedding-001",
        google_api_key=OPENAI_API_KEY
    )
    return embeddings.embed_query(text=text)


def get_huggingface_embedding(text: str):
    """
    Generate free embeddings using HuggingFace through LangChain.
    Model: all-MiniLM-L6-v2 (384-dim, free and fast)
    """
    model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    embedding = model.embed_query(text)
    return embedding
