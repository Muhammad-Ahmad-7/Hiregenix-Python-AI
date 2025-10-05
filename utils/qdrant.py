
from qdrant_client.models import VectorParams, Distance
from qdrant_client import QdrantClient


def connection_qdrant():
    # --- Setup Qdrant DB ---
    client = QdrantClient(host="localhost", port=6333)
    return client

def create_qdrant_collection(client, name: str):
    if not client.collection_exists(name):
        client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE),
        )
    
    print("Collection created successfully")
    return client