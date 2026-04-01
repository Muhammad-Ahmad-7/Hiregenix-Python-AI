
from qdrant_client.models import VectorParams, Distance
from qdrant_client import QdrantClient
from config.env import QDRANT_URL, QDRANT_API_KEY


def connection_qdrant():
    # --- Setup Qdrant DB ---
    client = QdrantClient(
        url=QDRANT_URL, 
        api_key=QDRANT_API_KEY,
    )
    return client

def create_qdrant_collection(client, name: str):
    if not client.collection_exists(name):
        client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE),
        )
    
    print("Collection created successfully")
    return client