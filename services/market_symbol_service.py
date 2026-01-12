"""Servicio para sincronizar símbolos de mercado en MongoDB.

Almacena por símbolo: nombre, símbolo, precio actual, precio de cierre,

cambio absoluto y porcentual, además de metadatos básicos de mercado.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
import logging

from db.mongo import get_db
from models.user import User
from services.market_screener_service import (
    market_screener_service,
    MarketScreenerServiceException,
)
from services.alpaca_service import alpaca_service, AlpacaServiceException

logger = logging.getLogger(__name__)


class MarketSymbolServiceException(Exception):
    """Errores propios del servicio de símbolos de mercado."""


class MarketSymbolService:
    """Servicio para persistir símbolos de mercado en MongoDB."""

    def __init__(self) -> None:
        db = get_db()
        self._collection = db["market_symbols"]
        self._collection.create_index("symbol", unique=True)

    @staticmethod
    def _normalize_symbol(symbol: Any) -> Optional[str]:
        if symbol is None:
            return None
        sym = str(symbol).strip().upper()
        return sym or None

    def _upsert_symbol(self, data: Dict[str, Any]) -> None:
        """Inserta o actualiza un símbolo en MongoDB."""
        symbol = self._normalize_symbol(data.get("symbol"))
        if not symbol:
            return

        now = datetime.utcnow()

        update: Dict[str, Any] = {
            "symbol": symbol,
            "name": data.get("name"),
            "market": data.get("market"),
            "price": data.get("price"),
            "close": data.get("close"),
            "change": data.get("change"),
            "percent_change": data.get("percent_change"),
            "direction": data.get("direction"),
            "volume": data.get("volume"),
            "trade_count": data.get("trade_count"),
            "last_screener_timestamp": data.get("last_updated"),
            "updated_at": now,
        }

        self._collection.update_one(
            {"symbol": symbol},
            {"$set": update, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )

    def sync_single_symbol_from_quote(self, symbol: str, user: Optional[User] = None) -> None:
        """Sincroniza un solo símbolo consultando su última cotización y barra diaria en Alpaca."""
        sym = self._normalize_symbol(symbol)
        if not sym:
            return

        try:
            quote = alpaca_service.get_last_quote(sym, user=user)
        except AlpacaServiceException as e:
            logger.error("Error de Alpaca al sincronizar símbolo %s: %s", sym, str(e))
            raise MarketSymbolServiceException(
                f"Error de Alpaca al sincronizar símbolo {sym}: {str(e)}"
            ) from e
        except Exception as e:  # pragma: no cover - defensivo
            logger.error("Error inesperado al sincronizar símbolo %s: %s", sym, str(e))
            raise MarketSymbolServiceException(
                f"Error inesperado al sincronizar símbolo {sym}: {str(e)}"
            ) from e

        # El snapshot ya incluye daily_bar y latest_trade.
        # Ya no necesitamos llamar a get_bars por separado si el snapshot tiene la info.
        volume = quote.get("volume")
        trade_count = quote.get("trade_count")
        
        # Si por alguna razón no viniera en el quote (aunque get_last_quote lo intenta),
        # solo entonces podríamos intentar un fallback, pero por ahora simplificamos.

        data: Dict[str, Any] = {
            "symbol": quote.get("symbol") or sym,
            "name": quote.get("name"),
            "market": None,
            "price": quote.get("price"),
            "close": quote.get("close"),
            "change": None,
            "percent_change": None,
            "direction": None,
            "volume": volume,
            "trade_count": trade_count,
            "last_updated": quote.get("timestamp"),
        }

        price = data.get("price")
        close = data.get("close")
        if price is not None and close is not None and close != 0:
            try:
                change = float(price) - float(close)
                percent_change = (change / float(close)) * 100.0
                data["change"] = change
                data["percent_change"] = percent_change
                # Calcular dirección basada en el cambio
                if change > 0:
                    data["direction"] = "up"
                elif change < 0:
                    data["direction"] = "down"
                else:
                    data["direction"] = "flat"
            except Exception:
                pass

        asset_class = quote.get("asset_class")
        if isinstance(asset_class, str):
            ac = asset_class.lower()
            if "equity" in ac or ac == "us_equity":
                data["market"] = "stocks"
            elif "crypto" in ac:
                data["market"] = "crypto"
            else:
                data["market"] = asset_class

        self._upsert_symbol(data)

    def upsert_from_most_actives(self, items: List[Dict[str, Any]]) -> int:
        """Actualiza/inserta símbolos a partir de resultados de most-actives."""
        try:
            symbols: Dict[str, Dict[str, Any]] = {}

            for item in items:
                sym = self._normalize_symbol(item.get("symbol"))
                if not sym:
                    continue

                entry = symbols.setdefault(sym, {})
                entry.update(
                    {
                        "symbol": sym,
                        "name": item.get("name"),
                        "market": item.get("market"),
                        "price": item.get("price"),
                        "close": item.get("close"),
                        "volume": item.get("volume"),
                        "trade_count": item.get("trade_count"),
                        "last_updated": item.get("last_updated"),
                    }
                )

                price = item.get("price")
                close = item.get("close")
                if price is not None and close is not None and close != 0:
                    change = float(price) - float(close)
                    percent_change = (change / float(close)) * 100.0
                    entry["change"] = change
                    entry["percent_change"] = percent_change

            processed = 0
            for data in symbols.values():
                self._upsert_symbol(data)
                processed += 1

            return processed
        except Exception as e:
            logger.error("Error al alimentar símbolos desde most-actives: %s", str(e))
            raise MarketSymbolServiceException(
                f"Error al alimentar símbolos desde most-actives: {str(e)}"
            ) from e

    def sync_from_screener(
        self,
        user: Optional[User] = None,
        top_most_actives: int = 50,
        top_movers: int = 50,
        market: str = "stocks",
    ) -> int:
        """Sincroniza símbolos desde Alpaca Screener API hacia MongoDB.

        Combina información de most-actives y market-movers y realiza upsert
        por símbolo.
        """
        try:
            symbols: Dict[str, Dict[str, Any]] = {}

            # 1) Most actives: nos dan volumen, trades, precio y cierre
            most_actives = market_screener_service.get_most_actives(
                user=user,
                by="volume",
                top=top_most_actives,
                market=market,
            )

            for item in most_actives:
                sym = self._normalize_symbol(item.get("symbol"))
                if not sym:
                    continue

                entry = symbols.setdefault(sym, {})
                entry.update(
                    {
                        "symbol": sym,
                        "name": item.get("name"),
                        "market": item.get("market"),
                        "price": item.get("price"),
                        "close": item.get("close"),
                        "volume": item.get("volume"),
                        "trade_count": item.get("trade_count"),
                        "last_updated": item.get("last_updated"),
                    }
                )

                price = item.get("price")
                close = item.get("close")
                if price is not None and close is not None and close != 0:
                    change = float(price) - float(close)
                    percent_change = (change / float(close)) * 100.0
                    entry["change"] = change
                    entry["percent_change"] = percent_change

            # 2) Market movers: priorizamos cambio y porcentaje
            movers = market_screener_service.get_market_movers(
                user=user,
                top=top_movers,
                market=market,
            )

            for mover in movers.get("gainers", []) + movers.get("losers", []):
                sym = self._normalize_symbol(mover.get("symbol"))
                if not sym:
                    continue

                entry = symbols.setdefault(sym, {})
                entry.update(
                    {
                        "symbol": sym,
                        "market": mover.get("market", entry.get("market")),
                        "price": mover.get("price", entry.get("price")),
                        "close": mover.get("close", entry.get("close")),
                        "change": mover.get("change", entry.get("change")),
                        "percent_change": mover.get(
                            "percent_change", entry.get("percent_change")
                        ),
                        "direction": mover.get("direction", entry.get("direction")),
                        "last_updated": mover.get("last_updated", entry.get("last_updated")),
                    }
                )

            processed = 0
            for data in symbols.values():
                self._upsert_symbol(data)
                processed += 1

            return processed
        except MarketScreenerServiceException as e:
            logger.error("Error de screener al sincronizar símbolos: %s", str(e))
            raise MarketSymbolServiceException(
                f"Error al sincronizar símbolos desde screener: {str(e)}"
            ) from e
        except Exception as e:  # pragma: no cover - defensivo
            logger.error("Error inesperado al sincronizar símbolos: %s", str(e))
            raise MarketSymbolServiceException(
                f"Error inesperado al sincronizar símbolos: {str(e)}"
            ) from e


market_symbol_service = MarketSymbolService()
