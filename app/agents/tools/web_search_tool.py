import logging
import urllib.parse
from html.parser import HTMLParser
from typing import List, Dict, Any, Optional
# pyrefly: ignore [missing-import]
import httpx
from app.config import get_settings

logger = logging.getLogger(__name__)


class _DDGHTMLParser(HTMLParser):
    """
    Lightweight HTML parser for DuckDuckGo HTML search results.
    """
    def __init__(self):
        super().__init__()
        self.results: List[Dict[str, str]] = []
        self._in_title = False
        self._in_snippet = False
        self._current_title = ""
        self._current_snippet = ""
        self._current_url = ""

    def handle_starttag(self, tag: str, attrs: list):
        attrs_dict = dict(attrs)
        cls = attrs_dict.get("class", "")
        if tag == "a" and "result__snippet" in cls:
            self._in_snippet = True
            self._current_snippet = ""
        elif tag == "a" and "result__a" in cls:
            self._in_title = True
            self._current_title = ""
            raw_href = attrs_dict.get("href", "")
            # Extract actual destination URL from DDG redirect url (uddg=...)
            if "uddg=" in raw_href:
                try:
                    parsed = urllib.parse.parse_qs(urllib.parse.urlparse(raw_href).query)
                    self._current_url = parsed.get("uddg", [raw_href])[0]
                except Exception:
                    self._current_url = raw_href
            else:
                self._current_url = raw_href

    def handle_endtag(self, tag: str):
        if tag == "a" and self._in_title:
            self._in_title = False
        elif tag == "a" and self._in_snippet:
            self._in_snippet = False
            if self._current_title and self._current_snippet:
                self.results.append({
                    "title": self._current_title.strip(),
                    "snippet": self._current_snippet.strip(),
                    "url": self._current_url.strip()
                })

    def handle_data(self, data: str):
        if self._in_title:
            self._current_title += data
        elif self._in_snippet:
            self._current_snippet += data


class SubscriptionWebSearchTool:
    """
    Real-Time Web Search Tool for live subscription pricing, active discounts,
    promotional bundle deals, and competitor alternatives.
    """

    SEARCH_ENDPOINT = "https://html.duckduckgo.com/html/"
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    }

    def __init__(self):
        self.settings = get_settings()

    async def search_subscription_deals(
        self,
        service_name: str,
        category: Optional[str] = None,
        max_results: Optional[int] = None
    ) -> List[Dict[str, str]]:
        """
        Executes a live web search for current plans, discounts, or competitor deals.
        """
        if not self.settings.ENABLE_LIVE_WEB_SEARCH:
            logger.info("Live web search is disabled by configuration.")
            return []

        limit = max_results or self.settings.WEB_SEARCH_MAX_RESULTS
        timeout_sec = self.settings.WEB_SEARCH_TIMEOUT_SECONDS

        # Construct a targeted search query for subscription optimization
        query = f"{service_name} subscription plans pricing discount alternatives"
        if category:
            query += f" {category}"

        try:
            async with httpx.AsyncClient(timeout=timeout_sec, verify=False) as client:
                response = await client.get(
                    self.SEARCH_ENDPOINT,
                    params={"q": query},
                    headers=self.HEADERS
                )

                if response.status_code != 200:
                    logger.warning("DuckDuckGo search returned status %d for '%s'", response.status_code, query)
                    return []

                parser = _DDGHTMLParser()
                parser.feed(response.text)

                results = parser.results[:limit]
                logger.info("Live web search found %d results for '%s'", len(results), service_name)
                return results

        except Exception as e:
            logger.warning("Live web search encountered an error for '%s': %s", service_name, e)
            return []

    async def get_live_deals_summary(self, service_names: List[str]) -> str:
        """
        Gathers live deals across a list of services and formats a clean text summary.
        """
        if not service_names or not self.settings.ENABLE_LIVE_WEB_SEARCH:
            return ""

        summary_parts = []
        for name in service_names[:3]:  # Limit to top 3 services to avoid excess latency
            results = await self.search_subscription_deals(name, max_results=2)
            if results:
                summary_parts.append(f"### Live Market Insights for {name}:")
                for item in results:
                    summary_parts.append(f"- **{item['title']}**: {item['snippet']} (Source: {item['url']})")

        return "\n".join(summary_parts)


_web_search_tool: Optional[SubscriptionWebSearchTool] = None


def get_web_search_tool() -> SubscriptionWebSearchTool:
    global _web_search_tool
    if _web_search_tool is None:
        _web_search_tool = SubscriptionWebSearchTool()
    return _web_search_tool
