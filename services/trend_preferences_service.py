from datetime import datetime
from typing import Dict
import logging

from db.mongo import get_db


logger = logging.getLogger(__name__)


DEFAULT_PROFILE = "corto"
DEFAULT_MODEL_TYPE = "xgboost"


class TrendPreferencesServiceException(Exception):
    pass


class TrendPreferencesService:
    def __init__(self) -> None:
        db = get_db()
        self._collection = db["user_trend_preferences"]
        self._collection.create_index("user_id", unique=True)

    @staticmethod
    def _normalize_profile(profile: str | None) -> str:
        if not profile:
            return DEFAULT_PROFILE
        key = str(profile).strip().lower()
        if key in {"intradia", "intradía"}:
            return "intradia"
        if key in {"largo", "long"}:
            return "largo"
        return DEFAULT_PROFILE

    @staticmethod
    def _normalize_model_type(model_type: str | None) -> str:
        if not model_type:
            return DEFAULT_MODEL_TYPE
        key = str(model_type).strip().lower()
        if key in {"rf", "random_forest", "random-forest"}:
            return "random_forest"
        return DEFAULT_MODEL_TYPE

    def get_preferences(self, user_id: str) -> Dict[str, str]:
        try:
            doc = self._collection.find_one({"user_id": user_id})
        except Exception as e:
            logger.error("Error al leer preferencias de tendencia: %s", e)
            raise TrendPreferencesServiceException("Error al leer preferencias de tendencia")

        if not doc:
            return {
                "profile": DEFAULT_PROFILE,
                "model_type": DEFAULT_MODEL_TYPE,
            }

        profile = self._normalize_profile(doc.get("profile"))
        model_type = self._normalize_model_type(doc.get("model_type"))

        return {
            "profile": profile,
            "model_type": model_type,
        }

    def set_preferences(self, user_id: str, profile: str | None, model_type: str | None) -> Dict[str, str]:
        normalized_profile = self._normalize_profile(profile)
        normalized_model_type = self._normalize_model_type(model_type)

        now = datetime.utcnow()
        try:
            self._collection.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "profile": normalized_profile,
                        "model_type": normalized_model_type,
                        "updated_at": now,
                    },
                    "$setOnInsert": {"created_at": now},
                },
                upsert=True,
            )
        except Exception as e:
            logger.error("Error al guardar preferencias de tendencia: %s", e)
            raise TrendPreferencesServiceException("Error al guardar preferencias de tendencia")

        return {
            "profile": normalized_profile,
            "model_type": normalized_model_type,
        }


trend_preferences_service = TrendPreferencesService()
