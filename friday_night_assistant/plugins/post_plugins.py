"""Plugin interface for PostAgent - specialized in blog post operations."""

from typing import Optional, List, Dict, Any
import logging

from friday_night_assistant.models.pg_models.models import Post, Category
from django.core.exceptions import FieldError

logger = logging.getLogger(__name__)


class PostAgentPlugins:
    """Helper methods for PostAgent functionality - specialized for blog posts."""

    def __init__(self):
        pass

    @staticmethod
    def get_available_methods() -> List[Dict[str, Any]]:
        """Return list of available methods for PostAgent."""
        return [
            {
                "name": "get_post_details",
                "description": "Get detailed information about a blog post by slug",
                "parameters": {
                    "slug": {
                        "type": "str",
                        "required": True,
                        "description": "The blog post slug"
                    }
                },
                "returns": "Dict with post details including title, body, status, categories"
            },
            {
                "name": "update_post_content",
                "description": "Update the content (body) of a blog post",
                "parameters": {
                    "slug": {
                        "type": "str",
                        "required": True,
                        "description": "The blog post slug"
                    },
                    "new_content": {
                        "type": "dict",
                        "required": True,
                        "description": "New content as JSON dict (e.g., {'en': '...', 'it': '...'})"
                    }
                },
                "returns": "Dict with success status and updated post info"
            },
            {
                "name": "get_post_categories",
                "description": "Get all categories associated with a blog post",
                "parameters": {
                    "slug": {
                        "type": "str",
                        "required": True,
                        "description": "The blog post slug"
                    }
                },
                "returns": "List of category names"
            },
            {
                "name": "analyze_post_quality",
                "description": "Analyze the quality of a blog post content",
                "parameters": {
                    "slug": {
                        "type": "str",
                        "required": True,
                        "description": "The blog post slug"
                    }
                },
                "returns": "Dict with quality metrics (word count, readability, etc.)"
            }
        ]

    @staticmethod
    def get_post_details(slug: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a blog post.

        Args:
            slug: The post slug to search for

        Returns:
            Dictionary with post details or None if not found
        """
        post = PostAgentPlugins._find_post_by_slug(slug)
        if not post:
            return None

        return {
            "id": post.id,
            "title": post.title,
            "body": post.body,
            "status": post.status,
            "counter": post.counter
        }

    @staticmethod
    def update_post_content(slug: str, new_content: Dict[str, Any]) -> Dict[str, Any]:
        """Update the content of a blog post.

        Args:
            slug: The post slug
            new_content: New content as dict

        Returns:
            Dict with success status
        """
        post = PostAgentPlugins._find_post_by_slug(slug)
        if not post:
            return {"error": f"Post with slug '{slug}' not found"}

        try:
            post.body = new_content
            post.save()
            logger.info(f"Post {slug} content updated successfully")
            return {
                "success": True,
                "message": f"Post '{slug}' updated successfully",
                "post_id": post.id
            }
        except Exception as e:
            logger.error(f"Error updating post {slug}: {e}")
            return {"error": str(e)}

    @staticmethod
    def get_post_categories(slug: str) -> List[str]:
        """Get all categories for a blog post.

        Args:
            slug: The post slug

        Returns:
            List of category names
        """
        post = PostAgentPlugins._find_post_by_slug(slug)
        if not post:
            return []

        # This is a placeholder - you'll need to implement based on your actual schema
        # The categorizable table uses content_type and object_id
        try:
            from django.contrib.contenttypes.models import ContentType
            from friday_night_assistant.models.pg_models.models import Categorizable

            content_type = ContentType.objects.get_for_model(Post)
            categorizables = Categorizable.objects.filter(
                content_type=content_type,
                object_id=post.id
            ).select_related('category')

            return [cat.category.name for cat in categorizables]
        except Exception as e:
            logger.error(f"Error fetching categories for post {slug}: {e}")
            return []

    @staticmethod
    def analyze_post_quality(slug: str) -> Dict[str, Any]:
        """Analyze the quality of a blog post.

        Args:
            slug: The post slug

        Returns:
            Dict with quality metrics
        """
        post = PostAgentPlugins._find_post_by_slug(slug)
        if not post:
            return {"error": f"Post with slug '{slug}' not found"}

        analysis = {
            "slug": slug,
            "has_title": bool(post.title),
            "has_body": bool(post.body),
            "status": post.status,
            "view_count": post.counter
        }

        # Analyze body content if available
        if post.body:
            if isinstance(post.body, dict):
                analysis["languages"] = list(post.body.keys())
                analysis["word_counts"] = {}
                for lang, content in post.body.items():
                    if isinstance(content, str):
                        analysis["word_counts"][lang] = len(content.split())
            elif isinstance(post.body, str):
                analysis["word_count"] = len(post.body.split())

        return analysis

    @staticmethod
    def _find_post_by_slug(slug: str) -> Optional[Post]:
        """Find Post by slug with multiple fallback strategies.

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

