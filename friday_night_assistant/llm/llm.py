"""Simple LLM client for Ollama API."""

import json
import logging
import time
from typing import Any, Callable
from functools import wraps

import requests

logger = logging.getLogger(__name__)


def retry(max_retries: int = 3) -> Callable:
    """Decorator to retry a function on exception."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    # Retry only on network-related exceptions from requests
                    try:
                        from requests.exceptions import RequestException
                        is_network_error = isinstance(e, RequestException)
                    except Exception:
                        is_network_error = False

                    if not is_network_error:
                        # Non-retryable exception, raise immediately
                        raise

                    last_exception = e
                    logger.warning(f"Attempt {attempt}/{max_retries} failed: {e}")

            logger.error(f"Max retries ({max_retries}) exceeded")
            raise last_exception or Exception("Max retries exceeded")

        return wrapper

    return decorator


class LLMException(Exception):
    """Custom exception for LLM-related errors."""
    pass


class LLM:
    """Simple interface for Ollama API."""

    DEFAULT_MODEL = "gemma3"
    DEFAULT_API_URL = "http://localhost:11434/api/generate"

    def __init__(self, model: str = DEFAULT_MODEL, api_url: str = DEFAULT_API_URL):
        """
        Initialize LLM client.

        Args:
            model: Model name to use (e.g., 'mistral', 'llama2')
            api_url: Ollama API endpoint URL
        """
        self.model = model
        self.api_url = api_url

    @retry(max_retries=3)
    def generate(
            self,
            prompt: str,
            json_mode: bool = False,
            timeout: int = 120
    ) -> str:
        """
        Generate a response from the LLM.

        Args:
            prompt: Input prompt
            json_mode: Whether to return JSON format
            timeout: Request timeout in seconds

        Returns:
            Generated response text

        Raises:
            LLMException: On API errors
        """
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False
        }

        if json_mode:
            payload["format"] = "json"

        try:
            # Log diagnostics: prompt size and approximate payload size
            try:
                prompt_len = len(prompt)
            except Exception:
                prompt_len = None

            try:
                payload_size = len(json.dumps(payload))
            except Exception:
                payload_size = None

            logger.debug(f"LLM.generate: model={self.model} api_url={self.api_url} prompt_len={prompt_len} payload_size={payload_size} timeout={timeout}")

            start = time.time()
            response = requests.post(
                self.api_url,
                json=payload,
                timeout=timeout
            )
            duration = time.time() - start

            logger.debug(f"LLM.generate: request completed in {duration:.3f}s status={response.status_code}")

            response.raise_for_status()
            # Try to read raw text first for diagnostics
            raw_text = response.text
            try:
                result = response.json()
            except ValueError:
                logger.debug("LLM.generate: response is not valid JSON, returning raw text")
                # Log truncated response length
                logger.debug(f"LLM.generate: response_text_len={len(raw_text) if raw_text is not None else 'None'}")
                return raw_text

            # Log size of JSON response
            try:
                resp_size = len(json.dumps(result))
            except Exception:
                resp_size = None

            logger.debug(f"LLM.generate: json response size={resp_size}")

            return result.get("response", result)
        except requests.exceptions.RequestException as e:
            logger.error(f"Ollama API error: {e}")
            raise LLMException(f"Failed to generate response: {e}") from e

    def generate_json(self, prompt: str, timeout: int = 120) -> Any:
        """
        Generate and parse JSON response.

        Args:
            prompt: Input prompt
            timeout: Request timeout in seconds

        Returns:
            Parsed JSON object

        Raises:
            LLMException: On API or JSON parse errors
        """
        response = self.generate(prompt, json_mode=True, timeout=timeout)
        try:
            return json.loads(response)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            raise LLMException(f"Invalid JSON response: {e}") from e