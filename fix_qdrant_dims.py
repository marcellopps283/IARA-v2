from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams
import os

def fix_qdrant():
    client = QdrantClient(host="localhost", port=6333)
    collection_name = "mem0_core"
    
    print(f"Checking collection: {collection_name}")
    try:
        client.delete_collection(collection_name)
        print(f"Deleted old collection {collection_name}")
    except Exception as e:
        print(f"Could not delete (might not exist): {e}")

    print(f"Creating collection {collection_name} with 1024 dims...")
    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=1024, distance=Distance.COSINE),
    )
    print("✅ Collection recreated successfully!")

if __name__ == "__main__":
    fix_qdrant()
