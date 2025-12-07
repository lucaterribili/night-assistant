import json
import re
import logging
from typing import Optional, List, Dict, Any, Callable
from functools import wraps

import requests

from .prompts.translate import TRANSLATE_PROMPT
from .prompts.reprocess import REPROCESS_PROMPT
from .prompts.sell_discussion import SELL_DISCUSSION_PROMPT
from .prompts.discussion import DISCUSSION_PROMPT
from .prompts.semantic_question import SEMANTIC_QUESTION_PROMPT
from .prompts.semantic_answer import SEMANTIC_ANSWER_PROMPT
from .prompts.summary import SUMMARY_PROMPT
from .prompts.simple_summary import SIMPLE_SUMMARY_PROMPT
from .prompts.take_inspiration import TAKE_INSPIRATION_PROMPT
from .prompts.correct_json import CORRECT_JSON_PROMPT
from .prompts.intent import INTENT_PROMPT
from .prompts.article import ARTICLE_PROMPT

# Configure logging
logging.basicConfig(level=logging.INFO)
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
                    last_exception = e
                    logger.warning(f"Attempt {attempt}/{max_retries} failed: {e}")

            logger.error(f"Max retries ({max_retries}) exceeded")
            raise last_exception or Exception("Max retries exceeded")

        return wrapper

    return decorator


class LLMException(Exception):
    """Custom exception for LLM-related errors."""
    pass


class LlmResponse:
    """Helper class for processing LLM responses."""

    @staticmethod
    def normalize_list_response(output: Any) -> List:
        """
        Normalize output to a list format.

        Args:
            output: Response from LLM (string or list)

        Returns:
            Normalized list or empty list on error
        """
        if isinstance(output, list):
            return output

        try:
            return json.loads(output)
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Failed to parse response as JSON: {e}")
            return []


class LLM:
    """
    Main LLM interface class for generating various types of content.

    Supports translation, discussion generation, semantic analysis,
    summarization, and more through a local Mistral model.
    """

    DEFAULT_MODEL = "mistral"
    DEFAULT_API_URL = "http://localhost:11434/api/generate"

    def __init__(self, model: str = DEFAULT_MODEL, api_url: str = DEFAULT_API_URL):
        """
        Initialize LLM client.

        Args:
            model: Model name to use
            api_url: API endpoint URL
        """
        self.model = model
        self.api_url = api_url
        self.response = LlmResponse()

    def generate_response(
            self,
            prompt: str,
            response_format: Optional[str] = None,
            timeout: int = 120
    ) -> str:
        """
        Generate a response from the LLM.

        Args:
            prompt: Input prompt
            response_format: Format type ("json_object" for JSON)
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

        if response_format == "json_object":
            payload["format"] = "json"

        try:
            response = requests.post(
                self.api_url,
                json=payload,
                timeout=timeout
            )
            response.raise_for_status()
            result = response.json()
            return result["response"]
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            raise LLMException(f"Failed to generate response: {e}") from e

    @staticmethod
    def generate_example_json(number: int) -> str:
        """
        Generate example JSON structure for Q&A pairs.

        Args:
            number: Number of Q&A pairs

        Returns:
            JSON string with example structure
        """
        example = []
        for i in range(1, number + 1):
            example.append(f"Domanda {i}?")
            example.append(f"Risposta {i}")
        return json.dumps(example, ensure_ascii=False)

    def translate(self, text: str, from_lang: str, to_lang: str) -> str:
        """Translate text from one language to another."""
        prompt = TRANSLATE_PROMPT.format(
            from_lang=from_lang,
            to_lang=to_lang,
            text=text
        )
        return self.generate_response(prompt)

    def prompt(self, basic_prompt: str, input_text: str) -> str:
        """Process text with a custom prompt."""
        prompt = REPROCESS_PROMPT.format(
            basic_prompt=basic_prompt,
            input_text=input_text
        )
        return self.generate_response(prompt)

    def generate_sell_discussion(self, text: str, number: int = 18) -> List:
        """Generate sales discussion Q&A pairs."""
        example_json = self.generate_example_json(number)
        prompt = SELL_DISCUSSION_PROMPT.format(
            text=text,
            example_json=example_json
        )
        output = self.generate_response(prompt, response_format="json_object")
        return self.response.normalize_list_response(output)

    @retry(max_retries=3)
    def generate_discussion(
            self,
            text: str,
            number: Optional[int] = None,
            title: Optional[str] = None
    ) -> List:
        """
        Generate discussion Q&A pairs.

        Args:
            text: Content to generate discussion from
            number: Number of Q&A pairs to generate
            title: Optional topic title

        Returns:
            List of alternating questions and answers
        """
        prompt = self._build_discussion_prompt(text, number, title)
        output = self.generate_response(prompt, response_format="json_object")
        validated_output = self._validate_discussion_json(output)

        if validated_output is None:
            raise LLMException("Failed to generate valid discussion JSON")

        return self.response.normalize_list_response(validated_output)

    def generate_semantic_question(self, question: str) -> str:
        """Generate semantic analysis of a question."""
        prompt = SEMANTIC_QUESTION_PROMPT.format(question=question)
        return self.generate_response(prompt, response_format="json_object")

    def generate_semantic_answer(self, answer: str) -> str:
        """Generate semantic analysis of an answer."""
        prompt = SEMANTIC_ANSWER_PROMPT.format(answer=answer)
        return self.generate_response(prompt, response_format="json_object")

    def generate_summary(self, title: str, content: str) -> str:
        """Generate a summary with title and content."""
        prompt = SUMMARY_PROMPT.format(title=title, content=content)
        return self.generate_response(prompt)

    def generate_simple_summary(
            self,
            content: str,
            entities: Optional[List[str]] = None
    ) -> str:
        """
        Generate a simple summary, optionally replacing entities.

        Args:
            content: Content to summarize
            entities: Optional list of entities to replace

        Returns:
            Summarized text
        """
        entities_part = (
            f'Sostituisci nel nuovo testo queste parole chiavi {entities} '
            f'con altre a tua scelta.'
            if entities else ''
        )
        prompt = SIMPLE_SUMMARY_PROMPT.format(
            content=content,
            entities_part=entities_part
        )
        return self.generate_response(prompt)

    def take_inspiration(
            self,
            content: str,
            is_question: bool = False,
            entities: Optional[List[str]] = None
    ) -> str:
        """
        Generate new content inspired by input.

        Args:
            content: Source content
            is_question: Whether content is a question to paraphrase
            entities: Entities to replace

        Returns:
            Generated content
        """
        if is_question:
            content_part = (
                f'Parafrasa questa domanda: "{content}" '
                f'con una forma semantica equivalente\n'
                f'Devi cambiare tutti gli eventuali numeri, nomi propri '
                f'ed eventuali date'
            )
        else:
            content_part = (
                f'Prendi inspirazione da questo contenuto: "{content}"\n'
                f'Scrivi un altro contenuto su un altro argomento della '
                f'stessa lunghezza. \n'
                f'Devi cambiare tutti gli eventuali numeri, nomi propri '
                f'ed eventuali date presenti nel contenuto originale.\n'
            )

        entities_part = (
            f'Queste parole presenti nel testo originale, "{entities}" '
            f'devono essere assolutamente sostituite con altre a tua scelta.'
            if entities else ''
        )

        prompt = TAKE_INSPIRATION_PROMPT.format(
            content_part=content_part,
            entities_part=entities_part
        )
        return self.generate_response(prompt)

    @retry(max_retries=3)
    def correct_json_task(
            self,
            task_input: str,
            task_output: str,
            task_type: str = 'discussion',
            critical: bool = True
    ) -> List:
        """
        Correct malformed JSON output from a task.

        Args:
            task_input: Original task input
            task_output: Output to correct
            task_type: Type of task
            critical: Whether to use critical correction mode

        Returns:
            Corrected and validated list
        """
        task_part = (
            f'Ho dato al mio modello il seguente task: '
            f'{self._build_discussion_prompt(text=task_input)}"\n'
            if task_type == 'discussion' else ''
        )

        critical_part = (
            f'Tieni presente che il modello PyTorch commette molti errori, '
            f'quindi la tua predizione sul testo in input deve guidare '
            f'la correzione.\n'
            if critical else ''
        )

        prompt = CORRECT_JSON_PROMPT.format(
            task_part=task_part,
            task_output=task_output,
            critical_part=critical_part
        )
        output = self.generate_response(prompt, response_format="json_object")
        validated_output = self._validate_discussion_json(output)

        if validated_output is None:
            raise LLMException("Failed to correct JSON")

        return self.response.normalize_list_response(validated_output)

    def generate_intent(
            self,
            question: str,
            generated_intents: List[Dict[str, str]]
    ) -> str:
        """
        Generate intent classification for a question.

        Args:
            question: Question to classify
            generated_intents: List of existing intents

        Returns:
            Generated intent
        """
        intents_list = '\n'.join([
            f'**Name: {intent["name"]} - Title: {intent["title"]}**'
            for intent in generated_intents
        ])

        intents_list_part = (
            f'È fondamentale che il name generato non sia già presente '
            f'in questa lista:\n{intents_list}\n\n'
            if intents_list else ''
        )

        prompt = INTENT_PROMPT.format(
            question=question,
            intents_list_part=intents_list_part
        )
        return self.generate_response(prompt)

    def generate_article(self, title: str) -> str:
        """Generate an article from a title."""
        prompt = ARTICLE_PROMPT.format(title=title)
        return self.generate_response(prompt)

    def send_message(self, message: str) -> str:
        """Send a direct message to the LLM."""
        return self.generate_response(message)

    @staticmethod
    def _validate_discussion_json(json_string: str) -> Optional[List[str]]:
        """
        Validate and clean discussion JSON.

        Args:
            json_string: JSON string to validate

        Returns:
            Validated list or None on error
        """
        try:
            discussion = json.loads(json_string)

            # Remove placeholder items
            discussion = [
                item for item in discussion
                if not re.fullmatch(
                    r"(?i)(Domanda|Risposta|Question|Answer) \d{1,5}",
                    item
                )
            ]

            # Clean items: remove parentheses content and extra spaces
            discussion = [
                re.sub(r"\s+", " ", re.sub(r"\(.*?\)", "", item)).strip()
                for item in discussion
            ]

            # Validate even number of elements (Q&A pairs)
            if len(discussion) % 2 != 0:
                logger.warning(
                    f"Discussion has odd number of elements: {len(discussion)}"
                )
                raise ValueError(
                    "The number of elements in the discussion must be even."
                )

            return discussion

        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"JSON validation failed: {e}")
            return None

    def _build_discussion_prompt(
            self,
            text: str,
            number: Optional[int] = None,
            title: Optional[str] = None
    ) -> str:
        """
        Build a discussion generation prompt.

        Args:
            text: Content text
            number: Number of Q&A pairs
            title: Optional topic title

        Returns:
            Formatted prompt string
        """
        title_part = (
            f'L\'argomento trattato è: "{title}". '
            f'Ogni domanda deve essere semanticamente collegata al titolo.\n'
            if title else ''
        )

        if number:
            number_part = (
                f'L\'array deve contenere esattamente {number * 2} elementi, '
                f'alternando domande e risposte in sequenza.\n'
                f'Formato JSON richiesto: {self.generate_example_json(number)} \n'
            )
        else:
            number_part = (
                f'L\'array deve contenere domande e risposte alternate '
                f'in sequenza.\n'
                f'Formato JSON richiesto: {self.generate_example_json(5)} \n'
            )

        return DISCUSSION_PROMPT.format(
            text=text,
            title_part=title_part,
            number_part=number_part
        )