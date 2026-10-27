"""Optional ONNX local embeddings and symmetric int8 cosine storage."""
from __future__ import annotations

import array
import math
import os
import struct
from pathlib import Path

MODEL = "BAAI/bge-small-en-v1.5"
MODEL_REPO = "qdrant/bge-small-en-v1.5-onnx-q"
MODEL_REVISION = "aa8f8b060edb00e03bfdd08813a2949946c8ba55"


def pack(vector) -> bytes:
    values = list(map(float, vector))
    scale = max(map(abs, values), default=0) / 127 or 1
    q = array.array("b", (max(-127, min(127, round(v / scale))) for v in values))
    norm = math.sqrt(sum(v*v for v in q)) or 1
    return struct.pack("<f", norm) + q.tobytes()


def cosine(a: bytes, b: bytes) -> float:
    if len(a) != len(b):
        raise ValueError("embedding dimension mismatch")
    av, bv = array.array("b", a[4:]), array.array("b", b[4:])
    return sum(x*y for x, y in zip(av, bv)) / (struct.unpack("<f", a[:4])[0] * struct.unpack("<f", b[:4])[0])


class LocalEmbedder:
    def __init__(self, cache_dir: Path, *, download=False):
        os.environ["ORT_DISABLE_TELEMETRY"] = "1"
        os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
        os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
        os.environ["HF_HOME"] = str(cache_dir / "huggingface")
        os.environ["HF_HUB_OFFLINE"] = "0" if download else "1"
        try:
            import onnxruntime
            onnxruntime.disable_telemetry_events()
            from fastembed import TextEmbedding
        except ImportError as exc:
            raise ValueError("Install semantic support: pip install 'ravel-index[semantic]'") from exc
        from huggingface_hub import snapshot_download, constants
        # Explicit public/no-auth calls also protect API hosts which imported HF
        # before RAVEL configured its environment. Never consult an implicit token.
        constants.HF_HUB_DISABLE_TELEMETRY = True
        constants.HF_HUB_DISABLE_IMPLICIT_TOKEN = True
        snapshot = snapshot_download(repo_id=MODEL_REPO, revision=MODEL_REVISION,
                                     cache_dir=str(cache_dir), token=False, local_files_only=not download,
                                     allow_patterns=["config.json", "tokenizer.json", "tokenizer_config.json",
                                                     "special_tokens_map.json", "model_optimized.onnx"])
        self.model = TextEmbedding(model_name=MODEL, cache_dir=str(cache_dir), threads=2,
                                   local_files_only=True, specific_model_path=str(snapshot))

    def embed(self, texts, *, query=False):
        texts = list(texts)
        if query:
            texts = ["Represent this sentence for searching relevant passages: " + t for t in texts]
        return [pack(v) for v in self.model.embed(texts, batch_size=16)]
