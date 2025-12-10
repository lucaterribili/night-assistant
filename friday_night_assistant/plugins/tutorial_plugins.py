"""Plugin interface for TutorialAgent - specialized in tutorial operations."""

from typing import Optional, List, Dict, Any
import logging
import html2text
import unicodedata
import html

from friday_night_assistant.models.pg_models.models import Tutorial


logger = logging.getLogger(__name__)


class TutorialAgentPlugins:
    """Helper methods for TutorialAgent functionality - specialized for tutorials."""

    def __init__(self):
        pass

    @staticmethod
    def get_available_methods() -> List[Dict[str, Any]]:
        """Return list of available methods for TutorialAgent."""
        return [
            {
                "name": "get_tutorial_details",
                "description": "Get detailed information about a tutorial by slug",
                "parameters": {
                    "slug": {
                        "type": "str",
                        "required": True,
                        "description": "The tutorial slug"
                    }
                },
                "returns": "Dict with tutorial details including title, body, status, categories"
            },
            {
                "name": "update_tutorial_content",
                "description": "Update the content (body) of a tutorial",
                "parameters": {
                    "slug": {
                        "type": "str",
                        "required": True,
                        "description": "The tutorial slug"
                    },
                    "new_content": {
                        "type": "dict",
                        "required": True,
                        "description": "New content as JSON dict (e.g., {'en': '...', 'it': '...'})"
                    }
                },
                "returns": "Dict with success status and updated tutorial info"
            },
            {
                "name": "get_tutorial_categories",
                "description": "Get all categories associated with a tutorial",
                "parameters": {
                    "slug": {
                        "type": "str",
                        "required": True,
                        "description": "The tutorial slug"
                    }
                },
                "returns": "List of category names"
            },
            {
                "name": "analyze_tutorial_structure",
                "description": "Analyze the structure and completeness of a tutorial",
                "parameters": {
                    "slug": {
                        "type": "str",
                        "required": True,
                        "description": "The tutorial slug"
                    }
                },
                "returns": "Dict with structure metrics (sections, code blocks, images, etc.)"
            },
            {
                "name": "check_tutorial_prerequisites",
                "description": "Check if tutorial has proper prerequisites and setup instructions",
                "parameters": {
                    "slug": {
                        "type": "str",
                        "required": True,
                        "description": "The tutorial slug"
                    }
                },
                "returns": "Dict with prerequisites check results"
            }
        ]

    @staticmethod
    def get_tutorial_details(slug: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a tutorial.

        Args:
            slug: The tutorial slug to search for

        Returns:
            Dictionary with tutorial details or None if not found
        """
        tutorial = TutorialAgentPlugins._find_tutorial_by_slug(slug)
        if not tutorial:
            return None

        body = tutorial.body
        if isinstance(body, dict):
            # Convert each language's HTML to Markdown
            markdown_body = {}
            for lang, content in body.items():
                if isinstance(content, str):
                    # Step 1: Unescape HTML entities (e.g., &ugrave; -> ù)
                    unescaped_content = html.unescape(content)
                    # Step 2: Normalize UTF-8
                    normalized_content = unicodedata.normalize('NFC', unescaped_content)
                    # Step 3: Convert to Markdown
                    markdown = html2text.html2text(normalized_content)
                    # Step 4: Replace single \n with space, but keep \n\n
                    markdown = markdown.replace('\n\n', '<<<DOUBLE_NEWLINE>>>').replace('\n', ' ').replace('<<<DOUBLE_NEWLINE>>>', '\n\n')
                    markdown_body[lang] = markdown
                else:
                    markdown_body[lang] = content
            body = markdown_body
        elif isinstance(body, str):
            # Step 1: Unescape HTML entities
            unescaped_body = html.unescape(body)
            # Step 2: Normalize UTF-8
            normalized_body = unicodedata.normalize('NFC', unescaped_body)
            # Step 3: Convert to Markdown
            markdown = html2text.html2text(normalized_body)
            # Step 4: Replace single \n with space, but keep \n\n
            body = markdown.replace('\n\n', '<<<DOUBLE_NEWLINE>>>').replace('\n', ' ').replace('<<<DOUBLE_NEWLINE>>>', '\n\n')

        return {
            "id": tutorial.id,
            "title": tutorial.title,
            "body": body,
            "status": tutorial.status
        }

    @staticmethod
    def update_tutorial_content(slug: str, new_content: Dict[str, Any]) -> Dict[str, Any]:
        """Update the content of a tutorial.

        Args:
            slug: The tutorial slug
            new_content: New content as dict

        Returns:
            Dict with success status
        """
        tutorial = TutorialAgentPlugins._find_tutorial_by_slug(slug)
        if not tutorial:
            return {"error": f"Tutorial with slug '{slug}' not found"}

        try:
            tutorial.body = new_content
            tutorial.save()
            logger.info(f"Tutorial {slug} content updated successfully")
            return {
                "success": True,
                "message": f"Tutorial '{slug}' updated successfully",
                "tutorial_id": tutorial.id
            }
        except Exception as e:
            logger.error(f"Error updating tutorial {slug}: {e}")
            return {"error": str(e)}

    @staticmethod
    def get_tutorial_categories(slug: str) -> List[str]:
        """Get all categories for a tutorial.

        Args:
            slug: The tutorial slug

        Returns:
            List of category names
        """
        tutorial = TutorialAgentPlugins._find_tutorial_by_slug(slug)
        if not tutorial:
            return []

        try:
            from django.contrib.contenttypes.models import ContentType
            from friday_night_assistant.models.pg_models.models import Categorizable

            content_type = ContentType.objects.get_for_model(Tutorial)
            categorizables = Categorizable.objects.filter(
                content_type=content_type,
                object_id=tutorial.id
            ).select_related('category')

            return [cat.category.name for cat in categorizables]
        except Exception as e:
            logger.error(f"Error fetching categories for tutorial {slug}: {e}")
            return []

    @staticmethod
    def analyze_tutorial_structure(slug: str) -> Dict[str, Any]:
        """Analyze the structure of a tutorial.

        Args:
            slug: The tutorial slug

        Returns:
            Dict with structure metrics
        """
        tutorial = TutorialAgentPlugins._find_tutorial_by_slug(slug)
        if not tutorial:
            return {"error": f"Tutorial with slug '{slug}' not found"}

        analysis = {
            "slug": slug,
            "has_title": bool(tutorial.title),
            "has_body": bool(tutorial.body),
            "status": tutorial.status
        }

        # Analyze body content if available
        if tutorial.body:
            if isinstance(tutorial.body, dict):
                analysis["languages"] = list(tutorial.body.keys())
                analysis["structure_by_language"] = {}

                for lang, content in tutorial.body.items():
                    if isinstance(content, str):
                        lang_analysis = TutorialAgentPlugins._analyze_content_structure(content)
                        analysis["structure_by_language"][lang] = lang_analysis
            elif isinstance(tutorial.body, str):
                analysis["structure"] = TutorialAgentPlugins._analyze_content_structure(tutorial.body)

        return analysis

    @staticmethod
    def check_tutorial_prerequisites(slug: str) -> Dict[str, Any]:
        """Check if tutorial has prerequisites and setup instructions.

        Args:
            slug: The tutorial slug

        Returns:
            Dict with prerequisites check
        """
        tutorial = TutorialAgentPlugins._find_tutorial_by_slug(slug)
        if not tutorial:
            return {"error": f"Tutorial with slug '{slug}' not found"}

        check_results = {
            "slug": slug,
            "has_prerequisites": False,
            "has_setup": False,
            "has_requirements": False
        }

        if tutorial.body:
            content_str = ""
            if isinstance(tutorial.body, dict):
                # Check in English version first, or any available
                content_str = tutorial.body.get('en', '') or next(iter(tutorial.body.values()), '')
            elif isinstance(tutorial.body, str):
                content_str = tutorial.body

            if content_str:
                content_lower = content_str.lower()
                check_results["has_prerequisites"] = any(
                    keyword in content_lower
                    for keyword in ["prerequisite", "prerequisites", "before you start", "requirements"]
                )
                check_results["has_setup"] = any(
                    keyword in content_lower
                    for keyword in ["setup", "installation", "install", "getting started"]
                )
                check_results["has_requirements"] = any(
                    keyword in content_lower
                    for keyword in ["require", "need", "must have"]
                )

        return check_results

    @staticmethod
    def _analyze_content_structure(content: str) -> Dict[str, Any]:
        """Analyze the structure of tutorial content.

        Args:
            content: The tutorial content string (Markdown)

        Returns:
            Dict with structure information
        """
        return {
            "word_count": len(content.split()),
            "char_count": len(content),
            "has_code_blocks": "```" in content,
            "heading_count": content.count("# "),
            "list_count": content.count("- ") + content.count("* "),
            "link_count": content.count("["),
            "image_count": content.count("![")
        }

    @staticmethod
    def _find_tutorial_by_slug(slug: str) -> Optional[Tutorial]:
        """Find Tutorial by slug in any language.

        Args:
            slug: The tutorial slug to search for

        Returns:
            Tutorial object if found, None otherwise
        """
        try:
            # PostgreSQL JSONB: cerca il valore in qualsiasi chiave del campo slug
            tutorial = Tutorial.objects.filter(
                slug__isnull=False
            ).extra(
                where=["EXISTS (SELECT 1 FROM jsonb_each_text(slug) WHERE value = %s)"],
                params=[slug]
            ).first()

            if tutorial:
                return tutorial

            logger.warning(f"Tutorial not found for slug: {slug}")
            return None

        except Exception as e:
            logger.error(f"Error searching tutorial by slug '{slug}': {e}")
            return None
