"""Recreate the notion_chunks Qdrant collection and upload BGE-M3 vectors."""

from __future__ import annotations

import asyncio
import argparse
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from src.db.models import DocChunk, RawDocument
from src.db.session import AsyncSessionLocal, engine
from src.rag.embedding import DEVICE, load_bge_model


COLLECTION_NAME = "notion_chunks"
VECTOR_SIZE = 1024
BATCH_SIZE = 4


async def load_chunks() -> list[tuple[int, int, str, dict[str, Any], str]]:
    try:
        async with AsyncSessionLocal() as session:
            rows = await session.execute(
                select(
                    DocChunk.id,
                    DocChunk.document_id,
                    DocChunk.content,
                    DocChunk.metadata_json,
                    RawDocument.title,
                )
                .join(RawDocument, RawDocument.id == DocChunk.document_id)
                .order_by(DocChunk.id)
            )
            return [
                (chunk_id, document_id, content, metadata or {}, title or "")
                for chunk_id, document_id, content, metadata, title in rows.all()
            ]
    finally:
        await engine.dispose()


def _batches(values: list[Any], size: int):
    for start in range(0, len(values), size):
        yield values[start : start + size]


def index_chunks(
    chunks: list[tuple[int, int, str, dict[str, Any], str]], *, recreate: bool = False
) -> int:
    from qdrant_client import QdrantClient, models
    qdrant_url = os.getenv("QDRANT_URL")
    api_key = os.getenv("QDRANT_API_KEY")
    if not qdrant_url:
        raise RuntimeError("QDRANT_URL is missing from the environment")
    if not api_key:
        raise RuntimeError("QDRANT_API_KEY is missing from the environment")
    if not chunks:
        raise RuntimeError("doc_chunks is empty; run scripts/create_chunks.py first")

    client = QdrantClient(url=qdrant_url, api_key=api_key, timeout=120)
    try:
        collection_exists = client.collection_exists(COLLECTION_NAME)
        if recreate and collection_exists:
            client.delete_collection(COLLECTION_NAME)
            collection_exists = False
        if collection_exists:
            collection = client.get_collection(COLLECTION_NAME)
            vector_config = collection.config.params.vectors
            if not isinstance(vector_config, models.VectorParams) or vector_config.size != VECTOR_SIZE:
                raise RuntimeError(
                    f"Collection {COLLECTION_NAME} exists with an incompatible vector configuration; "
                    "rerun with --recreate to replace it"
                )
            existing_ids: set[int] = set()
            offset = None
            while True:
                points, offset = client.scroll(
                    collection_name=COLLECTION_NAME,
                    limit=1000,
                    offset=offset,
                    with_payload=False,
                    with_vectors=False,
                )
                existing_ids.update(int(point.id) for point in points)
                if offset is None:
                    break
        else:
            existing_ids = set()
            client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=models.VectorParams(
                    size=VECTOR_SIZE,
                    distance=models.Distance.COSINE,
                ),
            )

        pending_chunks = [row for row in chunks if row[0] not in existing_ids]
        print(
            f"Chunks read: {len(chunks)}; already present: {len(existing_ids)}; "
            f"to upload: {len(pending_chunks)}",
            flush=True,
        )
        if not pending_chunks:
            total = client.count(collection_name=COLLECTION_NAME, exact=True).count
            print(f"Vectors uploaded in this run: 0")
            print(f"Vectors in {COLLECTION_NAME}: {total}")
            return total

        model = load_bge_model()
        print(f"Encoding batches of {BATCH_SIZE} on {DEVICE}", flush=True)

        uploaded = 0
        for batch in _batches(pending_chunks, BATCH_SIZE):
            vectors = model.encode(
                [row[2] for row in batch],
                batch_size=BATCH_SIZE,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            points = []
            for row, vector in zip(batch, vectors, strict=True):
                chunk_id, document_id, content, metadata, title = row
                if len(vector) != VECTOR_SIZE:
                    raise ValueError(
                        f"Expected {VECTOR_SIZE}-dimensional BGE-M3 vector, got {len(vector)}"
                    )
                points.append(
                    models.PointStruct(
                        id=chunk_id,
                        vector=vector.tolist(),
                        payload={
                            "document_id": document_id,
                            "chunk_id": chunk_id,
                            "title": title,
                            "content": content,
                            "metadata": metadata,
                        },
                    )
                )
            client.upsert(collection_name=COLLECTION_NAME, points=points, wait=True)
            uploaded += len(points)
            print(f"Uploaded {len(existing_ids) + uploaded}/{len(chunks)} vectors", flush=True)

        total = client.count(collection_name=COLLECTION_NAME, exact=True).count
        print(f"Chunks read: {len(chunks)}")
        print(f"Vectors uploaded in this run: {uploaded}")
        print(f"Vectors in {COLLECTION_NAME}: {total}")
        return total
    finally:
        client.close()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Delete and recreate notion_chunks before indexing",
    )
    args = parser.parse_args()
    chunks = asyncio.run(load_chunks())
    index_chunks(chunks, recreate=args.recreate)


if __name__ == "__main__":
    main()
