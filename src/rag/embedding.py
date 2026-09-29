"""Shared BGE-M3 model configuration for indexing and retrieval."""

from __future__ import annotations

import os


MODEL_NAME = "BAAI/bge-m3"
DEVICE = "cpu"


def configure_torch_threads() -> None:
    """Use the same bounded CPU setup as the indexer."""
    import torch

    torch.set_num_threads(max(1, min(12, os.cpu_count() or 1)))
    try:
        torch.set_num_interop_threads(1)
    except RuntimeError:
        # Inter-op settings cannot be changed after torch has started parallel work.
        pass


def load_bge_model():
    configure_torch_threads()
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(MODEL_NAME, device=DEVICE)
