from datetime import datetime
from typing import List
import logging

from db.mongo import get_db


logger = logging.getLogger(__name__)


class SymbolPreferencesServiceException(Exception):
    pass


class SymbolPreferencesService:
    def __init__(self) -> None:
        db = get_db()
        self._collection = db["user_symbol_preferences"]
        self._collection.create_index("user_id", unique=True)

    @staticmethod
    def _normalize_symbols(symbols: List[str]) -> List[str]:
        cleaned: List[str] = []
        for s in symbols:
            if s is None:
                continue
            sym = str(s).strip().upper()
            if not sym:
                continue
            if sym not in cleaned:
                cleaned.append(sym)
        return cleaned

    def get_symbols(self, user_id: str) -> List[str]:
        doc = self._collection.find_one({"user_id": user_id})
        if not doc:
            return []
        symbols = doc.get("symbols") or []
        return [str(s) for s in symbols]

    def set_symbols(self, user_id: str, symbols: List[str]) -> List[str]:
        normalized = self._normalize_symbols(symbols)
        now = datetime.utcnow()
        self._collection.update_one(
            {"user_id": user_id},
            {
                "$set": {"symbols": normalized, "updated_at": now},
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )
        return normalized

    def add_symbols(self, user_id: str, symbols: List[str]) -> List[str]:
        if not symbols:
            return self.get_symbols(user_id)
        existing = self.get_symbols(user_id)
        combined = existing + list(symbols)
        return self.set_symbols(user_id, combined)

    def remove_symbols(self, user_id: str, symbols: List[str]) -> List[str]:
        if not symbols:
            return self.get_symbols(user_id)
        to_remove = set(self._normalize_symbols(symbols))
        existing = self.get_symbols(user_id)
        remaining = [s for s in existing if s not in to_remove]
        return self.set_symbols(user_id, remaining)

    def clear_symbols(self, user_id: str) -> List[str]:
        self._collection.delete_one({"user_id": user_id})
        return []


symbol_preferences_service = SymbolPreferencesService()
