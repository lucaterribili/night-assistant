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
                "description": "Get top URLs by bounce rate from Matomo analytics. IMPORTANT: Results include 'type' field. ALWAYS check the 'type' field before choosing the next method: if type='tutorial' call delegate_to_tutorial_agent, if type='blog' call delegate_to_post_agent.",
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
                "description": "Find a BLOG POST by slug. ONLY for type='blog'.",
                "parameters": {
                    "slug": {
                        "type": "str",
                        "required": True,
                        "description": "The blog post slug to search for"
                    }
                },
                "returns": "Post object (type 'blog') or None if not found"
            },
            {
                "name": "get_tutorial_by_slug",
                "description": "Find a TUTORIAL by slug. ONLY for type='tutorial'.",
                "parameters": {
                    "slug": {
                        "type": "str",
                        "required": True,
                        "description": "The tutorial slug to search for"
                    }
                },
                "returns": "Post object (type 'tutorial') or None if not found"
            },
            {
                "name": "delegate_to_post_agent",
                "description": "Delegate work to the specialized PostAgent for blog post operations. Use this when you need to analyze, improve, or modify a blog post.",
                "parameters": {
                    "slug": {
                        "type": "str",
                        "required": True,
                        "description": "The blog post slug"
                    },
                    "task": {
                        "type": "str",
                        "required": False,
                        "default": "analyze_and_improve",
                        "description": "Task for PostAgent: 'analyze', 'improve', 'update', etc."
                    }
                },
                "returns": "Result from PostAgent execution"
            },
            {
                "name": "delegate_to_tutorial_agent",
                "description": "Delegate work to the specialized TutorialAgent for tutorial operations. Use this when you need to analyze, improve, or modify a tutorial.",
                "parameters": {
                    "slug": {
                        "type": "str",
                        "required": True,
                        "description": "The tutorial slug"
                    },
                    "task": {
                        "type": "str",
                        "required": False,
                        "default": "analyze_and_improve",
                        "description": "Task for TutorialAgent: 'analyze', 'improve', 'check_structure', etc."
                    }
                },
                "returns": "Result from TutorialAgent execution"
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
    def get_tutorial_by_slug(slug: str) -> Optional[Post]:
        """Find a tutorial Post by slug with multiple fallback strategies.

        This method mirrors `get_post_by_slug` but restricts results to posts
        that are tutorials (expected `type == 'tutorial'`). The implementation
        is defensive: if the `type` field or specific lookups are not available
        on the model, it falls back to the same searches and verifies the
        returned object's `type` attribute.
        """
        # Strategy 1: Direct slug + type filter
        try:
            return Post.objects.get(slug=slug, type='tutorial')
        except (FieldError, Post.DoesNotExist):
            # If the type field does not exist or there is no exact match, continue
            pass
        except Exception as e:
            logger.debug(f"Direct tutorial lookup failed for slug={slug}: {e}")

        # Strategy 2: JSON fields search (prefer filtering by type when supported)
        for field in ["body", "title"]:
            try:
                # try with type filter first
                post = Post.objects.filter(type='tutorial', **{f"{field}__contains": {"slug": slug}}).first()
                if post:
                    logger.info(f"Tutorial post found via JSON field: {field}")
                    return post
            except FieldError:
                # Model may not support `type` or JSON lookup; try without type and then verify
                try:
                    post = Post.objects.filter(**{f"{field}__contains": {"slug": slug}}).first()
                    if post and getattr(post, 'type', None) == 'tutorial':
                        logger.info(f"Tutorial post found via JSON field (post-verified): {field}")
                        return post
                except Exception:
                    continue
            except Exception as e:
                logger.debug(f"JSON tutorial search failed for field {field}: {e}")
                continue

        # Strategy 3: Case-insensitive text search, prefer type filtering
        for field in ["title", "body"]:
            try:
                post = Post.objects.filter(type='tutorial', **{f"{field}__icontains": slug}).first()
                if post:
                    logger.info(f"Tutorial post found via text search: {field}")
                    return post
            except FieldError:
                try:
                    post = Post.objects.filter(**{f"{field}__icontains": slug}).first()
                    if post and getattr(post, 'type', None) == 'tutorial':
                        logger.info(f"Tutorial post found via text search (post-verified): {field}")
                        return post
                except Exception:
                    continue
            except Exception as e:
                logger.debug(f"Text tutorial search failed for field {field}: {e}")
                continue

        logger.warning(f"Tutorial post not found for slug: {slug}")
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

        # Calculate bounce rate
        bounce_rate = AgentPlugins._extract_bounce_rate(page)

        return {
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

    @staticmethod
    def delegate_to_post_agent(slug: str, task: str = 'analyze_and_improve') -> Dict[str, Any]:
        """Delegate work to PostAgent for blog post operations.

        This method instantiates and runs the PostAgent with the specified slug and task.
        The PostAgent will autonomously decide which actions to take to complete the task.

        Args:
            slug: The blog post slug to work on
            task: The task type (optional, PostAgent will decide specific actions)

        Returns:
            Dictionary with execution results from PostAgent
        """
        try:
            from friday_night_assistant.management.commands.run_post_agent import Command as PostAgentCommand

            logger.info(f"Delegating to PostAgent: slug={slug}, task={task}")

            # Crea un'istanza del PostAgent
            post_agent = PostAgentCommand()

            # Esegui l'agente programmaticamente
            result = post_agent.execute(slug=slug, task=task)

            logger.info(f"PostAgent completed: {result}")
            return result

        except Exception as e:
            logger.error(f"Error delegating to PostAgent: {e}")
            return {
                'success': False,
                'error': str(e),
                'agent': 'PostAgent',
                'slug': slug
            }

    @staticmethod
    def delegate_to_tutorial_agent(slug: str, task: str = 'analyze_and_improve') -> Dict[str, Any]:
        """Delegate work to TutorialAgent for tutorial operations.

        This method instantiates and runs the TutorialAgent with the specified slug and task.
        The TutorialAgent will autonomously decide which actions to take to complete the task.

        Args:
            slug: The tutorial slug to work on
            task: The task type (optional, TutorialAgent will decide specific actions)

        Returns:
            Dictionary with execution results from TutorialAgent
        """
        try:
            from friday_night_assistant.management.commands.run_tutorial_agent import Command as TutorialAgentCommand

            logger.info(f"Delegating to TutorialAgent: slug={slug}, task={task}")

            # Crea un'istanza del TutorialAgent
            tutorial_agent = TutorialAgentCommand()

            # Esegui l'agente programmaticamente
            result = tutorial_agent.execute(slug=slug, task=task)

            logger.info(f"TutorialAgent completed: {result}")
            return result

        except Exception as e:
            logger.error(f"Error delegating to TutorialAgent: {e}")
            return {
                'success': False,
                'error': str(e),
                'agent': 'TutorialAgent',
                'slug': slug
            }

