from __future__ import annotations

from typing import Any, Dict, List, Optional
from urllib.parse import urljoin
import logging

import requests
from bs4 import BeautifulSoup


logger = logging.getLogger(__name__)


class NewsScraperServiceException(Exception):
    pass


class NewsScraperService:
    def __init__(self) -> None:
        self._session = requests.Session()

    @staticmethod
    def _normalize_symbol(symbol: Any) -> str:
        sym = str(symbol or "").strip().upper()
        if not sym:
            raise NewsScraperServiceException("Símbolo inválido")
        return sym

    @staticmethod
    def _candidate_urls(symbol: str) -> List[str]:
        base = "https://www.google.com/finance/quote/"
        if ":" in symbol:
            return [f"{base}{symbol}?hl=en"]
        if "-" in symbol:
            return [f"{base}{symbol}?hl=en"]

        exchanges = ["NASDAQ", "NYSE", "AMEX", "NYSEARCA", "BATS"]
        urls = [f"{base}{symbol}:{ex}?hl=en" for ex in exchanges]
        urls.append(f"{base}{symbol}?hl=en")
        return urls

    def get_news(self, symbol: Any, limit: int = 10) -> List[Dict[str, Any]]:
        sym = self._normalize_symbol(symbol)

        if limit <= 0:
            return []

        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "en-US,en;q=0.9",
        }

        last_error: Optional[Exception] = None
        for url in self._candidate_urls(sym):
            try:
                resp = self._session.get(url, headers=headers, timeout=12)
                if resp.status_code != 200:
                    continue

                soup = BeautifulSoup(resp.text, "html.parser")
                blocks = soup.find_all("div", {"class": "yY3Lee"})

                items: List[Dict[str, Any]] = []
                for block in blocks:
                    title_el = block.find("div", {"class": "Yfwt5"})
                    if not title_el:
                        continue
                    title = title_el.get_text(strip=True)
                    if not title:
                        continue

                    publisher_el = block.find("div", {"class": "sfyJob"})
                    date_el = block.find("div", {"class": "Adak"})
                    link_el = block.find("a", href=True)

                    href = link_el.get("href") if link_el else None
                    link = urljoin("https://www.google.com", href) if href else None

                    items.append(
                        {
                            "symbol": sym,
                            "title": title,
                            "publisher": publisher_el.get_text(strip=True) if publisher_el else None,
                            "date": date_el.get_text(strip=True) if date_el else None,
                            "url": link,
                            "source": "google_finance",
                        }
                    )

                    if len(items) >= limit:
                        break

                if items:
                    return items
            except Exception as e:
                last_error = e
                logger.debug("Error scraping news url=%s: %s", url, str(e))

        if last_error is not None:
            raise NewsScraperServiceException(
                f"No se pudieron obtener noticias para {sym}: {str(last_error)}"
            )

        raise NewsScraperServiceException(f"No se encontraron noticias para {sym}")


news_scraper_service = NewsScraperService()
