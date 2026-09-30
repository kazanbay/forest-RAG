"""Shared BGE-M3 model configuration for indexing and retrieval."""

from __future__ import annotations

import os
import torch

MODEL_NAME = "BAAI/bge-m3"

# Use CUDA when PyTorch can access it; half precision leaves room on 3 GB cards.
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


def configure_torch_threads() -> None:
    """Configure CPU thread allocation if running on CPU."""
    if DEVICE == "cpu":
        # Берём количество ядер системы (или 1, если os.cpu_count() вернул None)
        total_cores = os.cpu_count() or 1
        
        # Для CPU оптимально задействовать основные физические/логические потоки
        torch.set_num_threads(total_cores)
        
        try:
            torch.set_num_interop_threads(1)
        except RuntimeError:
            # Нельзя менять inter-op настройки, если PyTorch уже запустил параллельные задачи
            pass


def load_bge_model():
    configure_torch_threads()
    from sentence_transformers import SentenceTransformer

    print(f"Loading {MODEL_NAME} on {DEVICE}", flush=True)
    model_kwargs = {"torch_dtype": torch.float16} if DEVICE == "cuda" else {}
    return SentenceTransformer(MODEL_NAME, device=DEVICE, model_kwargs=model_kwargs)
