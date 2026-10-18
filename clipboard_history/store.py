import json
from pathlib import Path
from typing import Iterable


class ClipboardHistoryStore:
    def __init__(self, path: Path, max_items: int = 50, max_text_length: int = 10000):
        self.path = Path(path)
        self.max_items = max(1, int(max_items))
        self.max_text_length = max(1, int(max_text_length))
        self._items: list[str] = []
        self.load()

    def load(self):
        self._items = []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return

        if not isinstance(data, list):
            return
        for value in data:
            text = None
            if isinstance(value, str):
                text = value
            elif isinstance(value, dict) and isinstance(value.get("text"), str):
                text = value["text"]
            if text and self.is_valid_text(text) and text not in self._items:
                self._items.append(text)
        self._items = self._items[:self.max_items]

    def save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            payload = [{"text": text} for text in self._items]
            self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            return True
        except Exception:
            return False

    def add_text(self, text: str, save: bool = True) -> bool:
        if not self.is_valid_text(text):
            return False

        if text in self._items:
            self._items.remove(text)
        self._items.insert(0, text)
        del self._items[self.max_items:]
        if save:
            self.save()
        return True

    def clear(self):
        self._items.clear()
        self.save()

    def texts(self) -> list[str]:
        return list(self._items)

    def is_valid_text(self, text: str) -> bool:
        if not isinstance(text, str):
            return False
        if not text.strip():
            return False
        return len(text) <= self.max_text_length


def preview_text(text: str, limit: int = 120) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: max(0, limit - 1)] + "…"
