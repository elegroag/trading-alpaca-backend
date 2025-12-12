from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any

from bson import ObjectId
from pymongo.collection import Collection

from db.mongo import get_db


@dataclass
class User:
    id: Optional[str]
    email: str
    password_hash: str
    nombre: Optional[str] = None
    apellido: Optional[str] = None
    rol: str = "trader"
    alpaca_api_key_enc: Optional[str] = None
    alpaca_secret_key_enc: Optional[str] = None
    alpaca_base_url: Optional[str] = None
    paper_trading: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    last_login_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "email": self.email,
            "nombre": self.nombre,
            "apellido": self.apellido,
            "rol": self.rol,
            "alpaca_base_url": self.alpaca_base_url,
            "paper_trading": self.paper_trading,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
        }

    def to_mongo(self) -> Dict[str, Any]:
        doc: Dict[str, Any] = {
            "email": self.email,
            "password_hash": self.password_hash,
            "nombre": self.nombre,
            "apellido": self.apellido,
            "rol": self.rol,
            "alpaca_api_key_enc": self.alpaca_api_key_enc,
            "alpaca_secret_key_enc": self.alpaca_secret_key_enc,
            "alpaca_base_url": self.alpaca_base_url,
            "paper_trading": self.paper_trading,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_login_at": self.last_login_at,
        }
        if self.id is not None:
            doc["_id"] = ObjectId(self.id)
        return doc

    @classmethod
    def from_mongo(cls, doc: Dict[str, Any]) -> "User":
        return cls(
            id=str(doc.get("_id")) if doc.get("_id") is not None else None,
            email=doc.get("email", ""),
            password_hash=doc.get("password_hash", ""),
            nombre=doc.get("nombre"),
            apellido=doc.get("apellido"),
            rol=doc.get("rol", "trader"),
            alpaca_api_key_enc=doc.get("alpaca_api_key_enc"),
            alpaca_secret_key_enc=doc.get("alpaca_secret_key_enc"),
            alpaca_base_url=doc.get("alpaca_base_url"),
            paper_trading=bool(doc.get("paper_trading", True)),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
            last_login_at=doc.get("last_login_at"),
        )


def _get_collection() -> Collection:
    db = get_db()
    collection = db["users"]
    collection.create_index("email", unique=True)
    return collection


def create_user(user: User) -> User:
    collection = _get_collection()
    doc = user.to_mongo()
    result = collection.insert_one(doc)
    user.id = str(result.inserted_id)
    return user


def get_user_by_email(email: str) -> Optional[User]:
    collection = _get_collection()
    doc = collection.find_one({"email": email})
    if not doc:
        return None
    return User.from_mongo(doc)


def get_user_by_id(user_id: str) -> Optional[User]:
    collection = _get_collection()
    try:
        oid = ObjectId(user_id)
    except Exception:
        return None
    doc = collection.find_one({"_id": oid})
    if not doc:
        return None
    return User.from_mongo(doc)


def update_user_keys(
    user_id: str,
    alpaca_api_key_enc: Optional[str] = None,
    alpaca_secret_key_enc: Optional[str] = None,
    alpaca_base_url: Optional[str] = None,
    paper_trading: Optional[bool] = None,
) -> Optional[User]:
    collection = _get_collection()
    try:
        oid = ObjectId(user_id)
    except Exception:
        return None
    update: Dict[str, Any] = {"updated_at": datetime.utcnow()}
    if alpaca_api_key_enc is not None:
        update["alpaca_api_key_enc"] = alpaca_api_key_enc
    if alpaca_secret_key_enc is not None:
        update["alpaca_secret_key_enc"] = alpaca_secret_key_enc
    if alpaca_base_url is not None:
        update["alpaca_base_url"] = alpaca_base_url
    if paper_trading is not None:
        update["paper_trading"] = paper_trading
    doc = collection.find_one_and_update(
        {"_id": oid},
        {"$set": update},
        return_document=True,
    )
    if not doc:
        return None
    return User.from_mongo(doc)


def update_user_last_login(user_id: str) -> None:
    collection = _get_collection()
    try:
        oid = ObjectId(user_id)
    except Exception:
        return
    collection.update_one(
        {"_id": oid},
        {"$set": {"last_login_at": datetime.utcnow(), "updated_at": datetime.utcnow()}},
    )
