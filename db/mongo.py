from typing import Optional

from pymongo import MongoClient

from config import config

_client: Optional[MongoClient] = None


def get_client() -> MongoClient:
    global _client
    if _client is None:
        _client = MongoClient(config.MONGO_URI)
    return _client


def get_db():
    client = get_client()
    return client[config.MONGO_DB]
