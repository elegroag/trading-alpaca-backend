"""Servicio de screener de mercado usando Alpaca Screener API.

Proporciona métodos de alto nivel para obtener listas de acciones
más activas por volumen o número de trades.
"""

from typing import List, Dict, Any, Optional
import logging
from datetime import datetime

from alpaca.data.historical.screener import ScreenerClient
from alpaca.data.requests import MostActivesRequest, MarketMoversRequest, StockQuotesRequest, StockTradesRequest
from alpaca.data.enums import MostActivesBy, MarketType

from config import config
from models.user import User
from models.market_symbol import get_symbol_by_symbol
from utils.security import decrypt_text
from services.alpaca_service import alpaca_service, AlpacaServiceException

logger = logging.getLogger(__name__)


class MarketScreenerServiceException(Exception):
    """Errores propios del servicio de screener de mercado."""


class MarketScreenerService:
    """Servicio para consultar acciones más activas usando Alpaca Screener API."""

    def __init__(self) -> None:
        self._global_client = self._create_client(api_key=config.ALPACA_API_KEY, secret_key=config.ALPACA_SECRET_KEY)

    @staticmethod
    def _create_client(api_key: str, secret_key: str) -> ScreenerClient:
        return ScreenerClient(api_key=api_key or None, secret_key=secret_key or None)

    def _get_client_for_user(self, user: Optional[User]) -> ScreenerClient:
        if user and user.alpaca_api_key_enc and user.alpaca_secret_key_enc:
            try:
                api_key = decrypt_text(user.alpaca_api_key_enc)
                secret_key = decrypt_text(user.alpaca_secret_key_enc)
            except Exception as e:  # pragma: no cover - defensivo
                logger.error(f"Error al descifrar claves de Alpaca para screener: {str(e)}")
                raise MarketScreenerServiceException(
                    "No se pudieron descifrar las claves de Alpaca del usuario para screener"
                )
            return self._create_client(api_key=api_key, secret_key=secret_key)

        return self._global_client

    def get_most_actives(
        self,
        user: Optional[User] = None,
        by: str = "volume",
        top: int = 10,
        market: str = "stocks",
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Obtiene las acciones más activas.

        Args:
            user: Usuario autenticado (para usar sus claves Alpaca si existen).
            by: Métrica para ordenar ("volume" o "trades").
            top: Número de símbolos a devolver.
            market: Mercado ("stocks" o "crypto").

        Returns:
            Lista de diccionarios con información de cada acción.
        """
        try:
            client = self._get_client_for_user(user)

            by_normalized = by.lower()
            if by_normalized == "trades":
                by_enum = MostActivesBy.TRADES
            else:
                by_enum = MostActivesBy.VOLUME

            market_normalized = market.lower()
            if market_normalized == "crypto":
                market_enum = MarketType.CRYPTO
            else:
                market_enum = MarketType.STOCKS

            request = MostActivesRequest(
                most_actives_by=by_enum,
                top=int(top),
                market_type=market_enum,
            )

            result = client.get_most_actives(request)

            # result.most_actives es una lista de ActiveStock; mapeamos a dict
            items: List[Dict[str, Any]] = []
            last_updated = getattr(result, "last_updated", None)
            for item in getattr(result, "most_actives", []):
                # Intentar obtener un precio de cierre razonable si el tipo lo expone
                close_value = getattr(item, "prev_close", None)
                if close_value is None:
                    close_value = getattr(item, "previous_close", None)
                if close_value is None:
                    close_value = getattr(item, "close", None)

                items.append(
                    {
                        "symbol": getattr(item, "symbol", None),
                        "name": getattr(item, "name", None),
                        "volume": getattr(item, "volume", None),
                        "trade_count": getattr(item, "trade_count", None),
                        "price": getattr(item, "price", None),
                        "close": close_value,
                        "market": market_enum.value if hasattr(market_enum, "value") else str(market_enum),
                        "by": by_enum.value if hasattr(by_enum, "value") else str(by_enum),
                        "last_updated": last_updated.isoformat() if last_updated else None,
                    }
                )

            # Fallback: enriquecer precios usando cache de Mongo y, si hace falta, Alpaca
            for entry in items:
                symbol_entry = entry.get("symbol")
                if not symbol_entry:
                    continue

                needs_price = entry.get("price") is None
                needs_close = entry.get("close") is None
                needs_name = entry.get("name") is None
                if not (needs_price or needs_close or needs_name):
                    continue

                # 1) Intentar usar caché de Mongo (market_symbols) si está actualizada hoy
                try:
                    symbol_str = str(symbol_entry).strip().upper()
                    cached = get_symbol_by_symbol(symbol_str)
                except Exception:
                    cached = None

                if cached is not None and isinstance(getattr(cached, "updated_at", None), datetime):
                    try:
                        if cached.updated_at.date() == datetime.utcnow().date():
                            if needs_price and cached.price is not None:
                                entry["price"] = cached.price
                                needs_price = False
                            if needs_close and cached.close is not None:
                                entry["close"] = cached.close
                                needs_close = False
                            if needs_name and cached.name:
                                entry["name"] = cached.name
                                needs_name = False
                    except Exception:
                        # Si algo falla al validar la fecha, ignoramos la caché
                        pass

                if not (needs_price or needs_close or needs_name):
                    continue

                # 2) Si aún faltan datos, llamar a Alpaca para enriquecer
                try:
                    quote = alpaca_service.get_last_quote(str(symbol_entry), user=user)
                    if needs_price and quote.get("price") is not None:
                        entry["price"] = quote["price"]
                    if needs_close and quote.get("close") is not None:
                        entry["close"] = quote["close"]
                    if needs_name and quote.get("name"):
                        entry["name"] = quote["name"]
                except AlpacaServiceException as e:
                    logger.debug("No se pudo enriquecer precio de screener para %s: %s", symbol_entry, str(e))
                except Exception as e:  # pragma: no cover - defensivo
                    logger.debug("Error inesperado enriqueciendo precio de screener para %s: %s", symbol_entry, str(e))

            # 3) Aplicar filtro de precio mínimo/máximo si se especifica
            if min_price is not None or max_price is not None:
                filtered: List[Dict[str, Any]] = []
                for entry in items:
                    price_value = entry.get("price")
                    if price_value is None:
                        continue
                    try:
                        price_f = float(price_value)
                    except (TypeError, ValueError):
                        continue

                    if min_price is not None and price_f < min_price:
                        continue
                    if max_price is not None and price_f > max_price:
                        continue

                    filtered.append(entry)

                items = filtered

            return items
        except Exception as e:
            logger.error(f"Error al obtener most actives: {str(e)}")
            raise MarketScreenerServiceException(f"Error al obtener most actives: {str(e)}")

    def get_market_movers(
        self,
        user: Optional[User] = None,
        top: int = 10,
        market: str = "stocks",
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Obtiene los top market movers (ganadores y perdedores).

        Args:
            user: Usuario autenticado (para usar sus claves Alpaca si existen).
            top: Número de símbolos por lista (ganadores y perdedores).
            market: Mercado ("stocks" o "crypto").

        Returns:
            Dict con listas de gainers y losers.
        """
        try:
            client = self._get_client_for_user(user)

            market_normalized = market.lower()
            if market_normalized == "crypto":
                market_enum = MarketType.CRYPTO
            else:
                market_enum = MarketType.STOCKS

            request = MarketMoversRequest(
                market_type=market_enum,
                top=int(top),
            )

            result = client.get_market_movers(request)

            last_updated = getattr(result, "last_updated", None)
            last_updated_iso = last_updated.isoformat() if last_updated else None

            gainers: List[Dict[str, Any]] = []
            for mover in getattr(result, "gainers", []):
                close_value = getattr(mover, "prev_close", None)
                if close_value is None:
                    close_value = getattr(mover, "previous_close", None)
                if close_value is None:
                    close_value = getattr(mover, "close", None)

                gainers.append(
                    {
                        "symbol": getattr(mover, "symbol", None),
                        "percent_change": getattr(mover, "percent_change", None),
                        "change": getattr(mover, "change", None),
                        "price": getattr(mover, "price", None),
                        "close": close_value,
                        "direction": "gainer",
                        "market": market_enum.value if hasattr(market_enum, "value") else str(market_enum),
                        "last_updated": last_updated_iso,
                    }
                )

            losers: List[Dict[str, Any]] = []
            for mover in getattr(result, "losers", []):
                close_value = getattr(mover, "prev_close", None)
                if close_value is None:
                    close_value = getattr(mover, "previous_close", None)
                if close_value is None:
                    close_value = getattr(mover, "close", None)

                losers.append(
                    {
                        "symbol": getattr(mover, "symbol", None),
                        "percent_change": getattr(mover, "percent_change", None),
                        "change": getattr(mover, "change", None),
                        "price": getattr(mover, "price", None),
                        "close": close_value,
                        "direction": "loser",
                        "market": market_enum.value if hasattr(market_enum, "value") else str(market_enum),
                        "last_updated": last_updated_iso,
                    }
                )

            # Aplicar filtro de precio mínimo/máximo si se especifica
            if min_price is not None or max_price is not None:
                def _filter_price(entry: Dict[str, Any]) -> bool:
                    price_value = entry.get("price")
                    if price_value is None:
                        return False
                    try:
                        price_f = float(price_value)
                    except (TypeError, ValueError):
                        return False

                    if min_price is not None and price_f < min_price:
                        return False
                    if max_price is not None and price_f > max_price:
                        return False
                    return True

                gainers = [e for e in gainers if _filter_price(e)]
                losers = [e for e in losers if _filter_price(e)]

            return {
                "gainers": gainers,
                "losers": losers,
                "market": market_enum.value if hasattr(market_enum, "value") else str(market_enum),
                "last_updated": last_updated_iso,
            }
        except Exception as e:
            logger.error(f"Error al obtener market movers: {str(e)}")
            raise MarketScreenerServiceException(f"Error al obtener market movers: {str(e)}")


market_screener_service = MarketScreenerService()
