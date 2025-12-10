import os
import requests
from typing import Optional, Dict, Any, Callable


class MatomoClient:
    def __init__(self, base_url: Optional[str] = None, token: Optional[str] = None, timeout: int = 10):
        self.base_url = base_url or os.environ.get("MATOMO_URL")
        self.token = token or os.environ.get("MATOMO_AUTH_TOKEN")
        self.timeout = timeout
        if not self.base_url:
            raise ValueError("MATOMO_URL not set")
        if not self.token:
            raise ValueError("MATOMO_AUTH_TOKEN not set")
        if not self.base_url.endswith("/"):
            self.base_url += "/"

    def _api_request(self, params: Dict[str, Any], normalize: Optional[Callable] = None) -> Any:
        url = self.base_url + "index.php"
        fixed = {"module": "API", "format": "JSON"}
        full = {**params, **fixed}
        resp = requests.post(url, params=full, data={"token_auth": self.token}, timeout=self.timeout)
        resp.raise_for_status()
        try:
            data = resp.json()
        except Exception:
            raise RuntimeError("Matomo returned non-json: %s" % resp.text)

        if normalize:
            try:
                return normalize(data)
            except Exception:
                raise RuntimeError("Normalization failed")

        return data

    def get_visits(self, site_id: int, period: str = "day", date: str = "today"):
        return self._api_request({
            "method": "VisitsSummary.get",
            "idSite": site_id,
            "period": period,
            "date": date
        }, normalize=lambda d: {
            "visits": d.get("nb_visits")
        })

    def get_pageviews(self, site_id: int, period: str = "day", date: str = "today"):
        return self._api_request({
            "method": "Actions.get",
            "idSite": site_id,
            "period": period,
            "date": date
        }, normalize=lambda d: {
            "pageviews": d.get("nb_pageviews")
        })

    def get_top_pages(self, site_id: int, period: str = "day", date: str = "today", limit: int = 10):
        def norm(d):
            items = d if isinstance(d, list) else list(d.values())
            out = []
            for item in items[:limit]:
                url = item.get("url") or item.get("label") or "N/A"
                pv = item.get("nb_hits") or item.get("nb_visits")
                out.append({"url": url, "pageviews": pv})
            return out

        return self._api_request({
            "method": "Actions.getPageUrls",
            "idSite": site_id,
            "period": period,
            "date": date,
            # use flat=1 to return a flattened list of page URLs instead of hierarchical tree
            "flat": 1,
            "filter_limit": limit
        }, normalize=norm)

    def get_worst_bounce_urls(self, site_id: int, period: str = "day", date: str = "today", limit: int = 50):
        def norm(d):
            items = d if isinstance(d, list) else list(d.values())
            out = []
            for item in items[:limit]:
                url = item.get("url") or item.get("label") or item.get("pageUrl") or "N/A"
                b = item.get("bounce_rate")
                try:
                    b = float(b)
                except Exception:
                    pass
                out.append({"url": url, "bounce_rate": b})
            return out

        return self._api_request({
            "method": "Actions.getPageUrls",
            "idSite": site_id,
            "period": period,
            "date": date,
            # return flattened list so we get all page urls rather than only top-level nodes
            "flat": 1,
            "filter_sort_column": "bounce_rate",
            "filter_sort_order": "desc",
            "filter_limit": limit
        }, normalize=norm)
