from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional, List

from bson import ObjectId
from pymongo.collection import Collection

from db.mongo import get_db


@dataclass
class MarketSymbol:
    id: Optional[str]
    symbol: str
    name: Optional[str] = None
    market: Optional[str] = None
    price: Optional[float] = None
    close: Optional[float] = None
    change: Optional[float] = None
    percent_change: Optional[float] = None
    direction: Optional[str] = None
    volume: Optional[int] = None
    trade_count: Optional[int] = None
    last_screener_timestamp: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "symbol": self.symbol,
            "name": self.name,
            "market": self.market,
            "price": self.price,
            "close": self.close,
            "change": self.change,
            "percent_change": self.percent_change,
            "direction": self.direction,
            "volume": self.volume,
            "trade_count": self.trade_count,
            "last_screener_timestamp": self.last_screener_timestamp,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def to_mongo(self) -> Dict[str, Any]:
        doc: Dict[str, Any] = {
            "symbol": self.symbol.upper().strip(),
            "name": self.name,
            "market": self.market,
            "price": self.price,
            "close": self.close,
            "change": self.change,
            "percent_change": self.percent_change,
            "direction": self.direction,
            "volume": self.volume,
            "trade_count": self.trade_count,
            "last_screener_timestamp": self.last_screener_timestamp,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        if self.id is not None:
            doc["_id"] = ObjectId(self.id)
        return doc

    @classmethod
    def from_mongo(cls, doc: Dict[str, Any]) -> "MarketSymbol":
        return cls(
            id=str(doc.get("_id")) if doc.get("_id") is not None else None,
            symbol=str(doc.get("symbol", "")),
            name=doc.get("name"),
            market=doc.get("market"),
            price=doc.get("price"),
            close=doc.get("close"),
            change=doc.get("change"),
            percent_change=doc.get("percent_change"),
            direction=doc.get("direction"),
            volume=doc.get("volume"),
            trade_count=doc.get("trade_count"),
            last_screener_timestamp=doc.get("last_screener_timestamp"),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )


def _get_collection() -> Collection:
    db = get_db()
    collection = db["market_symbols"]
    collection.create_index("symbol", unique=True)
    return collection


def get_symbol_by_symbol(symbol: str) -> Optional[MarketSymbol]:
    col = _get_collection()
    doc = col.find_one({"symbol": symbol.upper().strip()})
    if not doc:
        return None
    return MarketSymbol.from_mongo(doc)


def list_symbols(limit: int = 1000) -> List[MarketSymbol]:
    col = _get_collection()
    cursor = col.find({}).sort("symbol", 1).limit(limit)
    return [MarketSymbol.from_mongo(doc) for doc in cursor]
