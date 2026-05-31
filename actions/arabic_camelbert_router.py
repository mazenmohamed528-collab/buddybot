from __future__ import annotations

import json
import os
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


DEFAULT_MODEL_NAME = "CAMeL-Lab/bert-base-arabic-camelbert-mix"
DEFAULT_MODEL_DIR = r"C:\dev\rasa_project\models\arabic_camelbert_intent_router"
DEFAULT_DEPENDENCY_PATH = r"E:\buddybot_camelbert_deps"
DEFAULT_THRESHOLD = 0.75

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
os.environ.setdefault("USE_FLAX", "0")
os.environ.setdefault("TRANSFORMERS_NO_FLAX", "1")

INTENT_TO_ROUTE = {
    "greeting": "conversational",
    "attendance_policy": "policy_rag",
    "gpa_query": "structured_sql",
    "academic_warning": "policy_rag",
    "schedule_query": "structured_sql",
    "student_lookup": "structured_sql",
    "educational": "educational_rag",
    "registration": "policy_rag",
    "fees_query": "policy_rag",
    "file_request": "file_retrieval",
}

ROUTE_LABELS = {
    "sql": "structured_sql",
    "structured_sql": "structured_sql",
    "database": "structured_sql",
    "educational_rag": "educational_rag",
    "knowledge": "educational_rag",
    "policy": "policy_rag",
    "policy_rag": "policy_rag",
    "regulation": "policy_rag",
    "file": "file_retrieval",
    "file_retrieval": "file_retrieval",
    "schedule_file": "file_retrieval",
    "conversation": "conversational",
    "conversational": "conversational",
    "chat": "conversational",
    "clarification": "clarification",
}


def normalize_arabic_text(text: str) -> str:
    value = unicodedata.normalize("NFKC", text or "")
    value = re.sub(r"[\u064b-\u065f\u0670]", "", value)
    value = value.replace("\u0640", "")
    for old, new in {"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ؤ": "و", "ئ": "ي"}.items():
        value = value.replace(old, new)
    return re.sub(r"\s+", " ", value).strip()


def contains_arabic_or_arabizi(text: str) -> bool:
    lowered = (text or "").lower()
    if re.search(r"[\u0600-\u06ff]", lowered):
        return True
    arabizi_hints = {
        "eih",
        "eh",
        "meen",
        "3ameed",
        "kolia",
        "koleya",
        "sa3at",
        "mo3tamda",
        "aqsam",
        "aksam",
        "talaba",
        "dof3a",
    }
    return bool(set(re.findall(r"[a-z0-9]+", lowered)) & arabizi_hints)


@dataclass
class CamelBertRoutePrediction:
    route: str
    confidence: float
    label: str
    source: str = "camelbert_arabic_router"


class CamelBertArabicRouter:
    """Optional Arabic transformer router for SQL/RAG/conversation decisions.

    The action server can run without torch/transformers. If a fine-tuned model is
    not configured, this class simply stays unavailable and the deterministic
    router in actions.py remains the fallback.
    """

    def __init__(
        self,
        model_dir: Optional[str] = None,
        threshold: Optional[float] = None,
        device: Optional[str] = None,
    ) -> None:
        self.model_dir = Path(model_dir or os.getenv("BUDDYBOT_ARABIC_ROUTER_MODEL_DIR", DEFAULT_MODEL_DIR))
        default_threshold = DEFAULT_THRESHOLD if threshold is None else threshold
        self.threshold = float(os.getenv("BUDDYBOT_ARABIC_ROUTER_THRESHOLD", default_threshold))
        self.device_name = device or os.getenv("BUDDYBOT_ARABIC_ROUTER_DEVICE")
        self._loaded = False
        self._available = False
        self._tokenizer: Any = None
        self._model: Any = None
        self._torch: Any = None
        self._id_to_label: Dict[int, str] = {}
        self._max_length = 128

    def is_available(self) -> bool:
        self._ensure_loaded()
        return self._available

    def predict(self, text: str) -> Optional[CamelBertRoutePrediction]:
        if not contains_arabic_or_arabizi(text):
            return None
        self._ensure_loaded()
        if not self._available:
            return None

        normalized = normalize_arabic_text(text)
        encoding = self._tokenizer(
            normalized,
            truncation=True,
            padding=True,
            max_length=self._max_length,
            return_tensors="pt",
        )
        encoding = {key: value.to(self._device) for key, value in encoding.items()}
        with self._torch.no_grad():
            logits = self._model(**encoding).logits
            probabilities = self._torch.softmax(logits, dim=1)[0].detach().cpu().numpy()
        label_id = int(probabilities.argmax())
        confidence = float(probabilities[label_id])
        label = self._id_to_label.get(label_id, str(label_id))
        route = self._label_to_route(label)
        if confidence < self.threshold or not route:
            return None
        return CamelBertRoutePrediction(route=route, confidence=confidence, label=label)

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        if not self.model_dir.exists():
            return
        dependency_path = os.getenv("BUDDYBOT_ARABIC_ROUTER_DEPENDENCY_PATH", DEFAULT_DEPENDENCY_PATH)
        if dependency_path and Path(dependency_path).exists() and dependency_path not in sys.path:
            sys.path.insert(0, dependency_path)
        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except Exception:
            return

        metadata = self._load_metadata()
        self._max_length = int(metadata.get("max_length", metadata.get("max_len", 128)))
        self._id_to_label = self._load_id_to_label(metadata)
        if not self._has_supported_label_schema(metadata):
            return
        self._torch = torch
        self._device = torch.device(self.device_name or ("cuda" if torch.cuda.is_available() else "cpu"))
        self._tokenizer = AutoTokenizer.from_pretrained(self.model_dir)
        self._model = AutoModelForSequenceClassification.from_pretrained(self.model_dir)
        self._model.to(self._device)
        self._model.eval()
        self._available = True

    def _load_metadata(self) -> Dict[str, Any]:
        for name in ["training_metadata.json", "router_metadata.json", "config.json"]:
            path = self.model_dir / name
            if path.exists():
                try:
                    return json.loads(path.read_text(encoding="utf-8"))
                except Exception:
                    return {}
        return {}

    def _load_id_to_label(self, metadata: Dict[str, Any]) -> Dict[int, str]:
        raw = metadata.get("id_to_label") or metadata.get("id2label")
        if isinstance(raw, dict):
            return {int(key): str(value) for key, value in raw.items()}
        label_map_path = self.model_dir / "label_map.json"
        if label_map_path.exists():
            label_map = json.loads(label_map_path.read_text(encoding="utf-8"))
            return {int(value): str(key) for key, value in label_map.items()}
        return {
            0: "structured_sql",
            1: "educational_rag",
            2: "policy_rag",
            3: "file_retrieval",
            4: "conversational",
            5: "clarification",
        }

    def _has_supported_label_schema(self, metadata: Dict[str, Any]) -> bool:
        """Reject unrelated fine-tunes, e.g. fraud/legitimate classifiers."""

        labels = {str(label).lower().strip() for label in self._id_to_label.values()}
        if not labels:
            return False
        unsupported = [label for label in labels if self._label_to_route(label) is None]
        if unsupported:
            return False
        purpose = str(metadata.get("purpose", "")).lower()
        return not purpose or "buddybot" in purpose

    @staticmethod
    def _label_to_route(label: str) -> Optional[str]:
        normalized = label.lower().strip()
        return INTENT_TO_ROUTE.get(normalized) or ROUTE_LABELS.get(normalized)


_ROUTER: Optional[CamelBertArabicRouter] = None


def predict_arabic_route(text: str) -> Optional[Dict[str, Any]]:
    global _ROUTER
    if _ROUTER is None:
        _ROUTER = CamelBertArabicRouter()
    prediction = _ROUTER.predict(text)
    if not prediction:
        return None
    return {
        "route": prediction.route,
        "confidence": prediction.confidence,
        "label": prediction.label,
        "source": prediction.source,
    }
