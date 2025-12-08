import os
import requests
from typing import Optional, Dict, Any


class MatomoClient:
    """Simple Matomo HTTP API client.

    Reads MATOMO_URL and MATOMO_AUTH_TOKEN from environment by default.

    Usage:
        client = MatomoClient()
        visits = client.get_visits(site_id=1, period="day", date="2025-01-01")
    """

    def __init__(self, base_url: Optional[str] = None, token: Optional[str] = None, timeout: int = 10):
        self.base_url = base_url or os.environ.get("MATOMO_URL")
        self.token = token or os.environ.get("MATOMO_AUTH_TOKEN")
        self.timeout = timeout

        if not self.base_url:
            raise ValueError("MATOMO_URL not set (either pass base_url or set MATOMO_URL env var)")
        if not self.token:
            raise ValueError("MATOMO_AUTH_TOKEN not set (either pass token or set MATOMO_AUTH_TOKEN env var)")

        # Normalize base url
        if not self.base_url.endswith("/"):
            self.base_url = self.base_url + "/"

    def _api_request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        params = params.copy()
        params.update({
            "module": "API",
            "format": "JSON",
            # token_auth moved to POST body per user request
        })
        url = self.base_url + "index.php"
        # Send a POST so the token can be supplied in the request body
        # Keep the API method/args in the query string (like the curl example) and put token_auth in the POST data
        data = {"token_auth": self.token}
        resp = requests.post(url, params=params, data=data, timeout=self.timeout)
        resp.raise_for_status()
        try:
            return resp.json()
        except ValueError:
            raise RuntimeError("Matomo returned non-json response: %s" % resp.text)

    def get_visits(self, site_id: int, period: str = "day", date: str = "today") -> Dict[str, Any]:
        """Return visits metric for a site_id for given period/date.

        site_id: 1,2,3
        period: day|week|month|year|range
        date: e.g. today, 2025-01-01, 2025-01-01,2025-01-31
        """
        params = {
            "method": "VisitsSummary.get",
            "idSite": site_id,
            "period": period,
            "date": date,
        }
        return self._api_request(params)

    def get_pageviews(self, site_id: int, period: str = "day", date: str = "today") -> Dict[str, Any]:
        params = {
            "method": "Actions.get",
            "idSite": site_id,
            "period": period,
            "date": date,
        }
        return self._api_request(params)

    def get_top_pages(self, site_id: int, period: str = "day", date: str = "today", limit: int = 10) -> Dict[str, Any]:
        params = {
            "method": "Actions.getPageUrls",
            "idSite": site_id,
            "period": period,
            "date": date,
            "filter_limit": limit,
        }
        return self._api_request(params)


# Small convenience function to iterate over known sites
def get_all_sites_data(client: MatomoClient, site_ids=(1, 2, 3), period: str = "day", date: str = "today"):
    results = {}
    for sid in site_ids:
        try:
            results[sid] = client.get_visits(site_id=sid, period=period, date=date)
        except Exception as e:
            # Avoid leaking the token in logs/errors. If the token appears in the exception text, redact it.
            err_text = str(e)
            try:
                token = getattr(client, "token", None)
                if token and token in err_text:
                    err_text = err_text.replace(token, "<REDACTED>")
            except Exception:
                pass
            results[sid] = {"error": err_text}
    return results
