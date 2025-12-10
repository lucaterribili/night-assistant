"""Plugin interface for agent integrations."""

from typing import Optional, List, Dict, Any
import logging

from friday_night_assistant.matomo.client import MatomoClient
from friday_night_assistant.models.pg_models.models import Post
from django.core.exceptions import FieldError

from friday_night_assistant.plugins.helpers import normalize_matomo_response

logger = logging.getLogger(__name__)


class AgentPlugins:
    """Helper methods for agent functionality."""

    def __init__(self, matomo_client: Optional[MatomoClient] = None):
        self.matomo = matomo_client or MatomoClient()

    @staticmethod
    def get_available_methods() -> List[Dict[str, Any]]:
        """Return list of available methods with their parameters and descriptions."""
        return [
            {
                "name": "get_top_bounce_urls",
                "description": "Get top URLs by bounce rate from Matomo analytics",
                "parameters": {
                    "site_id": {
                        "type": "int",
                        "required": True,
                        "description": "Matomo site ID"
                    },
                    "period": {
                        "type": "str",
                        "required": False,
                        "default": "day",
                        "description": "Time period: 'day', 'week', 'month', 'year'"
                    },
                    "date": {
                        "type": "str",
                        "required": False,
                        "default": "today",
                        "description": "Date or range: 'today', 'yesterday', 'YYYY-MM-DD'"
                    },
                    "limit": {
                        "type": "int",
                        "required": False,
                        "default": 5,
                        "description": "Number of results to return"
                    }
                },
                "returns": "List of dicts with 'url' and 'bounce_rate' keys"
            },
            {
                "name": "get_post_by_slug",
                "description": "Find a Post by slug using multiple search strategies",
                "parameters": {
                    "slug": {
                        "type": "str",
                        "required": True,
                        "description": "The post slug to search for"
                    }
                },
                "returns": "Post object or None if not found"
            }
        ]

    def get_top_bounce_urls(
        self,
        site_id: int,
        period: str = "day",
        date: str = "today",
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get top URLs by bounce rate from Matomo.

        Args:
            site_id: Matomo site identifier
            period: Time period for analytics ('day', 'week', 'month', 'year')
            date: Specific date or range ('today', 'yesterday', 'YYYY-MM-DD')
            limit: Maximum number of results to return

        Returns:
            List of dictionaries containing URL and bounce rate information

        Raises:
            Exception: If Matomo API call fails
        """
        try:
            # Request extra results to ensure we have enough after filtering
            pages = self.matomo.get_worst_bounce_urls(site_id, period, date, limit * 2)
        except Exception as e:
            logger.error(f"Matomo API error for site_id={site_id}: {e}")
            raise

        # Normalize and filter response to list of relevant pages (adds 'type' and optional 'slug')
        pages = normalize_matomo_response(pages)

        # Process and filter results
        results = []
        for page in pages:
            processed_page = self._process_page_data(page)
            if processed_page:
                results.append(processed_page)

        # Sort by bounce rate (highest first) and limit results
        results.sort(key=self._bounce_rate_sort_key)
        return results[:limit]

    @staticmethod
    def get_post_by_slug(slug: str) -> Optional[Post]:
        """Find Post by slug with multiple fallback strategies.

        Attempts to find a post using the following strategies in order:
        1. Direct slug field match
        2. JSON field search (body, title)
        3. Case-insensitive text search (title, body)

        Args:
            slug: The post slug to search for

        Returns:
            Post object if found, None otherwise
        """
        # Strategy 1: Direct slug field
        try:
            return Post.objects.get(slug=slug)
        except (FieldError, Post.DoesNotExist):
            pass

        # Strategy 2: JSON fields search
        for field in ["body", "title"]:
            try:
                post = Post.objects.filter(
                    **{f"{field}__contains": {"slug": slug}}
                ).first()
                if post:
                    logger.info(f"Post found via JSON field: {field}")
                    return post
            except Exception as e:
                logger.debug(f"JSON search failed for field {field}: {e}")
                continue

        # Strategy 3: Case-insensitive text search
        for field in ["title", "body"]:
            try:
                post = Post.objects.filter(
                    **{f"{field}__icontains": slug}
                ).first()
                if post:
                    logger.info(f"Post found via text search: {field}")
                    return post
            except Exception as e:
                logger.debug(f"Text search failed for field {field}: {e}")
                continue

        logger.warning(f"Post not found for slug: {slug}")
        return None

    @staticmethod
    def _process_page_data(page: Any) -> Optional[Dict[str, Any]]:
        """Process a single page entry from Matomo response.

        Args:
            page: Raw page data from Matomo API

        Returns:
            Processed page dictionary or None if invalid
        """
        # Skip non-dict items
        if not isinstance(page, dict):
            logger.warning(f"Skipping non-dict page item: {type(page).__name__}")
            return None

        # Extract URL
        url = page.get("label") or page.get("url")
        if not url:
            return None

        # Calculate bounce rate
        bounce_rate = AgentPlugins._extract_bounce_rate(page)

        return {
            "url": url,
            "bounce_rate": bounce_rate,
            **page
        }

    @staticmethod
    def _extract_bounce_rate(page: Dict[str, Any]) -> Optional[float]:
        """Extract and normalize bounce rate from page data.

        Args:
            page: Page dictionary from Matomo

        Returns:
            Bounce rate as percentage (0-100) or None if unavailable
        """
        # Try direct bounce rate fields
        bounce = page.get("bounce_rate") or page.get("bounceRate")

        # Calculate from bounce_count and nb_visits if needed
        if bounce is None and "bounce_count" in page and "nb_visits" in page:
            try:
                bounce_count = float(page["bounce_count"])
                nb_visits = float(page["nb_visits"])
                if nb_visits > 0:
                    bounce = (bounce_count / nb_visits) * 100
            except (ValueError, TypeError, ZeroDivisionError):
                return None

        # Normalize to 0-100 scale
        try:
            bounce = float(bounce) if bounce is not None else None
            if bounce is not None and 0 <= bounce <= 1:
                bounce = bounce * 100
            return bounce
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _bounce_rate_sort_key(item: Dict[str, Any]) -> float:
        """Generate sort key for bounce rate (highest first).

        Args:
            item: Dictionary with 'bounce_rate' key

        Returns:
            Negative bounce rate for descending sort, inf for None/invalid values
        """
        bounce_rate = item.get("bounce_rate")
        try:
            return -float(bounce_rate) if bounce_rate is not None else float('inf')
        except (ValueError, TypeError):
            return float('inf')

