
from qdrant_client.models import VectorParams, Distance
from qdrant_client import QdrantClient


def connection_qdrant():
    # --- Setup Qdrant DB ---
    client = QdrantClient(
        url="https://3f23e5b1-e25d-4fab-85bc-ad8b524c921c.eu-central-1-0.aws.cloud.qdrant.io:6333", 
        api_key="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.RgwGRYz6Mwom_DHpizYb_5rZLzWWW6r5saV8bZ7Nq-g",
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