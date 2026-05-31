from __future__ import annotations

import argparse
import json
import logging
import os
import random
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Sequence

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
os.environ.setdefault("USE_FLAX", "0")
os.environ.setdefault("TRANSFORMERS_NO_FLAX", "1")

DEFAULT_DEPENDENCY_PATH = r"E:\buddybot_camelbert_deps"
dependency_path = os.getenv("BUDDYBOT_ARABIC_ROUTER_DEPENDENCY_PATH", DEFAULT_DEPENDENCY_PATH)
if dependency_path and Path(dependency_path).exists() and dependency_path not in sys.path:
    sys.path.insert(0, dependency_path)

import numpy as np
import torch
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import train_test_split
from sklearn.utils.class_weight import compute_class_weight
from torch.optim import AdamW
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModelForSequenceClassification, AutoTokenizer, get_linear_schedule_with_warmup


LOGGER = logging.getLogger("camelbert_router_training")


def load_config(path: str) -> Dict[str, Any]:
    config_path = Path(path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["_config_dir"] = str(config_path.resolve().parent)
    config["_project_root"] = str(config_path.resolve().parents[1])
    return config


def resolve_path(config: Dict[str, Any], value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return Path(config["_project_root"]) / path


def setup_logging(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(output_dir / "training.log", encoding="utf-8"),
        ],
    )


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def normalize_arabic_text(text: str) -> str:
    value = unicodedata.normalize("NFKC", text or "")
    value = re.sub(r"[\u064b-\u065f\u0670]", "", value)
    value = value.replace("\u0640", "")
    for old, new in {"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ؤ": "و", "ئ": "ي"}.items():
        value = value.replace(old, new)
    return re.sub(r"\s+", " ", value).strip()


def load_jsonl(path: Path, label_to_id: Dict[str, int]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            item = json.loads(line)
            label = item.get("label")
            if label not in label_to_id:
                raise ValueError(f"Unknown label at line {line_number}: {label}")
            rows.append(
                {
                    "text": normalize_arabic_text(item["text"]),
                    "label": label,
                    "label_id": label_to_id[label],
                }
            )
    return rows


class RouterDataset(Dataset):
    def __init__(self, rows: Sequence[Dict[str, Any]], tokenizer: Any, max_length: int) -> None:
        self.labels = torch.tensor([row["label_id"] for row in rows], dtype=torch.long)
        self.encodings = tokenizer(
            [row["text"] for row in rows],
            truncation=True,
            padding=True,
            max_length=max_length,
            return_tensors="pt",
        )

    def __len__(self) -> int:
        return len(self.labels)

    def __getitem__(self, index: int) -> Dict[str, torch.Tensor]:
        return {
            "input_ids": self.encodings["input_ids"][index],
            "attention_mask": self.encodings["attention_mask"][index],
            "labels": self.labels[index],
        }


def make_loader(rows: Sequence[Dict[str, Any]], tokenizer: Any, config: Dict[str, Any], shuffle: bool, device: torch.device) -> DataLoader:
    dataset = RouterDataset(rows, tokenizer, int(config["max_length"]))
    return DataLoader(
        dataset,
        batch_size=int(config["batch_size"]),
        shuffle=shuffle,
        pin_memory=device.type == "cuda",
    )


def evaluate(model: Any, loader: DataLoader, loss_fn: Any, device: torch.device, use_amp: bool) -> Dict[str, Any]:
    model.eval()
    total_loss = 0.0
    labels: List[int] = []
    predictions: List[int] = []
    with torch.no_grad():
        for batch in loader:
            input_ids = batch["input_ids"].to(device, non_blocking=True)
            attention_mask = batch["attention_mask"].to(device, non_blocking=True)
            batch_labels = batch["labels"].to(device, non_blocking=True)
            with torch.cuda.amp.autocast(enabled=use_amp):
                outputs = model(input_ids=input_ids, attention_mask=attention_mask)
                loss = loss_fn(outputs.logits, batch_labels)
            total_loss += float(loss.item())
            batch_predictions = torch.argmax(outputs.logits, dim=1)
            labels.extend(batch_labels.cpu().numpy().tolist())
            predictions.extend(batch_predictions.cpu().numpy().tolist())
    return {
        "loss": total_loss / max(len(loader), 1),
        "accuracy": float(accuracy_score(labels, predictions)),
        "f1_macro": float(f1_score(labels, predictions, average="macro", zero_division=0)),
        "labels": labels,
        "predictions": predictions,
    }


def save_model(model: Any, tokenizer: Any, output_dir: Path, config: Dict[str, Any], metadata: Dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)
    serializable_config = {key: value for key, value in config.items() if not key.startswith("_")}
    (output_dir / "training_config.json").write_text(json.dumps(serializable_config, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "training_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "label_map.json").write_text(json.dumps(metadata["label_map"], ensure_ascii=False, indent=2), encoding="utf-8")


def train(config_path: str) -> None:
    config = load_config(config_path)
    output_dir = resolve_path(config, config["output_dir"])
    setup_logging(output_dir)
    set_seed(int(config["seed"]))

    labels = list(config["labels"])
    label_to_id = {label: index for index, label in enumerate(labels)}
    id_to_label = {index: label for label, index in label_to_id.items()}
    dataset_path = resolve_path(config, config["dataset_path"])
    rows = load_jsonl(dataset_path, label_to_id)
    label_ids = [row["label_id"] for row in rows]

    train_rows, temp_rows = train_test_split(
        rows,
        test_size=float(config["validation_size"]) + float(config["test_size"]),
        random_state=int(config["seed"]),
        stratify=label_ids,
    )
    temp_labels = [row["label_id"] for row in temp_rows]
    validation_ratio = float(config["validation_size"]) / (float(config["validation_size"]) + float(config["test_size"]))
    validation_rows, test_rows = train_test_split(
        temp_rows,
        test_size=1 - validation_ratio,
        random_state=int(config["seed"]),
        stratify=temp_labels,
    )

    device = torch.device("cuda" if torch.cuda.is_available() and config.get("use_cuda", True) else "cpu")
    use_amp = device.type == "cuda" and bool(config.get("mixed_precision", True))
    LOGGER.info("Training CAMeL-BERT Arabic router on %s. Device=%s", dataset_path, device)
    LOGGER.info("Rows: train=%s validation=%s test=%s", len(train_rows), len(validation_rows), len(test_rows))

    tokenizer = AutoTokenizer.from_pretrained(config["model_name"])
    model = AutoModelForSequenceClassification.from_pretrained(
        config["model_name"],
        num_labels=len(labels),
        id2label={index: label for index, label in id_to_label.items()},
        label2id=label_to_id,
    )
    model.to(device)

    train_loader = make_loader(train_rows, tokenizer, config, shuffle=True, device=device)
    validation_loader = make_loader(validation_rows, tokenizer, config, shuffle=False, device=device)
    test_loader = make_loader(test_rows, tokenizer, config, shuffle=False, device=device)

    class_weights = compute_class_weight("balanced", classes=np.arange(len(labels)), y=[row["label_id"] for row in train_rows])
    loss_fn = torch.nn.CrossEntropyLoss(weight=torch.tensor(class_weights, dtype=torch.float).to(device))
    optimizer = AdamW(model.parameters(), lr=float(config["learning_rate"]), weight_decay=float(config["weight_decay"]))
    total_steps = len(train_loader) * int(config["epochs"])
    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=int(float(config["warmup_ratio"]) * total_steps),
        num_training_steps=total_steps,
    )
    scaler = torch.cuda.amp.GradScaler(enabled=use_amp)

    best_score = -1.0
    bad_epochs = 0
    best_epoch = 0
    history: List[Dict[str, Any]] = []

    for epoch in range(1, int(config["epochs"]) + 1):
        model.train()
        train_loss = 0.0
        for batch in train_loader:
            optimizer.zero_grad(set_to_none=True)
            input_ids = batch["input_ids"].to(device, non_blocking=True)
            attention_mask = batch["attention_mask"].to(device, non_blocking=True)
            batch_labels = batch["labels"].to(device, non_blocking=True)
            with torch.cuda.amp.autocast(enabled=use_amp):
                outputs = model(input_ids=input_ids, attention_mask=attention_mask)
                loss = loss_fn(outputs.logits, batch_labels)
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            scaler.step(optimizer)
            scaler.update()
            scheduler.step()
            train_loss += float(loss.item())

        train_loss /= max(len(train_loader), 1)
        validation_metrics = evaluate(model, validation_loader, loss_fn, device, use_amp)
        row = {
            "epoch": epoch,
            "train_loss": train_loss,
            "validation_loss": validation_metrics["loss"],
            "validation_accuracy": validation_metrics["accuracy"],
            "validation_f1_macro": validation_metrics["f1_macro"],
        }
        history.append(row)
        LOGGER.info(
            "Epoch %s | train_loss=%.4f | val_loss=%.4f | val_acc=%.4f | val_f1_macro=%.4f",
            epoch,
            train_loss,
            validation_metrics["loss"],
            validation_metrics["accuracy"],
            validation_metrics["f1_macro"],
        )

        score = float(validation_metrics[config["monitor_metric"]])
        if score > best_score + float(config["early_stopping_min_delta"]):
            best_score = score
            best_epoch = epoch
            bad_epochs = 0
            metadata = {
                "model_name": config["model_name"],
                "purpose": config.get("purpose", "BuddyBot Arabic intent classifier"),
                "label_schema": config.get("label_schema", "buddybot_intent"),
                "route_map": config.get("route_map", {}),
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
                "best_epoch": best_epoch,
                "monitor_metric": config["monitor_metric"],
                "monitor_score": best_score,
                "max_length": int(config["max_length"]),
                "label_map": label_to_id,
                "id_to_label": {str(key): value for key, value in id_to_label.items()},
                "validation_metrics": {key: value for key, value in validation_metrics.items() if key not in {"labels", "predictions"}},
            }
            save_model(model, tokenizer, output_dir, config, metadata)
            LOGGER.info("Saved best Arabic router checkpoint to %s", output_dir)
        else:
            bad_epochs += 1
            if bad_epochs >= int(config["early_stopping_patience"]):
                LOGGER.info("Early stopping at epoch %s.", epoch)
                break

    best_model = AutoModelForSequenceClassification.from_pretrained(output_dir).to(device)
    test_metrics = evaluate(best_model, test_loader, loss_fn, device, use_amp)
    report = classification_report(
        test_metrics["labels"],
        test_metrics["predictions"],
        target_names=labels,
        output_dict=True,
        zero_division=0,
    )
    final_report = {
        "best_epoch": best_epoch,
        "best_validation_score": best_score,
        "test_accuracy": test_metrics["accuracy"],
        "test_f1_macro": test_metrics["f1_macro"],
        "classification_report": report,
        "history": history,
    }
    (output_dir / "final_report.json").write_text(json.dumps(final_report, ensure_ascii=False, indent=2), encoding="utf-8")
    LOGGER.info("Final test f1_macro=%.4f accuracy=%.4f", test_metrics["f1_macro"], test_metrics["accuracy"])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fine-tune CAMeL-BERT for BuddyBot Arabic hybrid routing.")
    parser.add_argument("--config", default="arabic_nlu/camelbert_intent_config.json")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    train(args.config)
