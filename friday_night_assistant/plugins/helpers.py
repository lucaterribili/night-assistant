"""Helpers per il filtraggio/normalizzazione delle risposte Matomo.

Fornisce:
- PATTERNS: regex per riconoscere pagine blog e tutorial
- normalize_matomo_response(pages): filtra la risposta Matomo mantenendo solo
  le pagine che matchano i pattern e aggiunge il campo `type` = 'blog'|'tutorial'.

Note sui pattern attuali:
- blog: /blog/<slug>  (esclude /blog/category/...) --> pattern: ^blog/(?P<slug>[^/]+)$
- tutorial: /tutorial/<slug> o /tutorial/<parent>/<tutorial_slug> -->
  pattern: ^tutorial/(?:[^/]+/)?(?P<slug>[^/]+)$

La funzione è robusta a risposte Matomo in formato list/dict e cerca il path
in `url`, `label` o `pageUrl`.
"""
from typing import Any, Dict, List, Optional, Tuple
import re
from urllib.parse import urlparse
import logging

logger = logging.getLogger(__name__)

# Lista di pattern (regex, type)
PATTERNS: List[Tuple[re.Pattern, str]] = [
    # match /blog/<slug> but not /blog/category/<...>
    (re.compile(r"^blog/(?P<slug>[^/]+)$", re.IGNORECASE), "blog"),
    # match /tutorial/<slug> and /tutorial/<parent>/<slug>
    (re.compile(r"^tutorial/(?:[^/]+/)?(?P<slug>[^/]+)$", re.IGNORECASE), "tutorial"),
]

# Chiavi da escludere dall'output finale
EXCLUDED_KEYS = {"url", "label", "pageUrl"}


def _extract_path_from_page(page: Dict[str, Any]) -> Optional[str]:
    """Estrae il path pulito (senza query) da una voce Matomo.

    Cerca le chiavi comuni: 'url', 'label', 'pageUrl'. Se il valore è un URL
    completo, viene parsato e ritorna solo il path.

    Args:
        page: dizionario contenente i dati della pagina Matomo

    Returns:
        path normalizzato senza leading/trailing slash, o None se non trovato
    """
    raw = _find_url_in_page(page)
    if not raw:
        return None

    path = _parse_url_to_path(raw)
    return _normalize_path(path)


def _find_url_in_page(page: Dict[str, Any]) -> Optional[str]:
    """Cerca l'URL nelle chiavi comuni di una voce Matomo.

    Args:
        page: dizionario contenente i dati della pagina

    Returns:
        valore URL grezzo o None
    """
    for key in ("url", "label", "pageUrl"):
        value = page.get(key)
        if value:
            return value
    return None


def _parse_url_to_path(raw_url: str) -> str:
    """Parsa un URL grezzo ed estrae il path.

    Args:
        raw_url: URL completo o path parziale

    Returns:
        path estratto, o l'input originale in caso di errore
    """
    try:
        parsed = urlparse(raw_url)
        return parsed.path or raw_url
    except Exception:
        return raw_url


def _normalize_path(path: str) -> str:
    """Normalizza un path rimuovendo slash iniziali e finali.

    Args:
        path: path da normalizzare

    Returns:
        path normalizzato
    """
    # Rimuovi trailing slash (eccetto per root)
    if path.endswith("/") and path != "/":
        path = path.rstrip("/")

    # Rimuovi leading slash per matching coerente
    return path.lstrip("/")


def _convert_pages_to_list(pages: Any) -> List[Dict[str, Any]]:
    """Converte l'input Matomo in una lista di dizionari.

    Args:
        pages: risposta grezza dall'API Matomo (dict, list, o singolo elemento)

    Returns:
        lista normalizzata di dizionari
    """
    # Se è un dict, estrai il campo 'result' o converti i values in lista
    if isinstance(pages, dict):
        pages = pages.get("result", list(pages.values()))

    # Se non è una lista, wrappalo in una lista
    if not isinstance(pages, list):
        pages = [pages]

    return pages


def _match_page_against_patterns(
    page: Dict[str, Any],
    path: str,
    patterns: List[Tuple[re.Pattern, str]]
) -> Optional[Dict[str, Any]]:
    """Prova a matchare una pagina contro i pattern disponibili.

    Args:
        page: dizionario originale della pagina
        path: path estratto e normalizzato
        patterns: lista di tuple (regex, type)

    Returns:
        dizionario annotato con type e slug (URL ancora presenti), o None se nessun match
    """
    for regex, ptype in patterns:
        match = regex.match(path)
        if not match:
            continue

        # Match trovato, annota la pagina (ma mantieni ancora gli URL)
        return _annotate_page_with_metadata(page, ptype, match)

    logger.debug("Page did not match any pattern: %s", path)
    return None


def _annotate_page_with_metadata(
    page: Dict[str, Any],
    page_type: str,
    regex_match: re.Match
) -> Dict[str, Any]:
    """Annota una pagina con type e slug estratto dal regex match.

    NOTA: mantiene ancora le chiavi URL - queste verranno rimosse dopo.

    Args:
        page: dizionario originale della pagina
        page_type: tipo della pagina ('blog', 'tutorial', etc.)
        regex_match: risultato del match regex

    Returns:
        nuovo dizionario con annotazioni aggiunte (URL ancora presenti)
    """
    # Crea copia della pagina
    new_page = page.copy()

    # Aggiungi il tipo
    new_page["type"] = page_type

    # Aggiungi slug se disponibile
    _add_slug_if_available(new_page, regex_match)

    return new_page


def _remove_url_keys(page: Dict[str, Any]) -> Dict[str, Any]:
    """Rimuove le chiavi URL da un dizionario pagina.

    Args:
        page: dizionario originale

    Returns:
        nuovo dizionario senza chiavi URL
    """
    return {k: v for k, v in page.items() if k not in EXCLUDED_KEYS}


def _add_slug_if_available(page: Dict[str, Any], regex_match: re.Match) -> None:
    """Aggiunge lo slug al dizionario se disponibile nel match.

    Args:
        page: dizionario da modificare (in-place)
        regex_match: risultato del match regex
    """
    try:
        groups = regex_match.groupdict()
        if "slug" in groups and regex_match.group("slug"):
            page["slug"] = regex_match.group("slug")
    except Exception as e:
        # Non critico, continua senza slug
        logger.debug("Failed to extract slug: %s", e)


def normalize_matomo_response(
    pages: Any,
    patterns: Optional[List[Tuple[re.Pattern, str]]] = None
) -> List[Dict[str, Any]]:
    """Normalizza e filtra una risposta Matomo.

    - Trasforma input dict/list/elemento singolo in lista di dict
    - Estrae il path da ogni voce e filtra usando i `patterns`
    - Aggiunge il campo 'type' con valore 'blog' o 'tutorial'
    - Aggiunge opzionalmente 'slug' se catturato dal regex
    - Rimuove le chiavi 'url', 'label', 'pageUrl' dall'output

    Args:
        pages: risposta grezza dall'API Matomo
        patterns: lista di tuple (compiled_regex, type). Se None usa PATTERNS

    Returns:
        lista di dict (voci Matomo annotate) contenente solo le pagine corrispondenti
        ai pattern richiesti, senza chiavi URL
    """
    patterns = patterns or PATTERNS

    # Normalizza input a lista
    pages_list = _convert_pages_to_list(pages)

    # Processa ogni pagina
    output: List[Dict[str, Any]] = []

    for page in pages_list:
        if not isinstance(page, dict):
            logger.debug("Skipping non-dict page item: %s", type(page))
            continue

        # Estrai path (usa le chiavi URL che sono ancora presenti)
        path = _extract_path_from_page(page)
        if not path:
            continue

        # Prova a matchare contro i pattern
        matched_page = _match_page_against_patterns(page, path, patterns)
        if matched_page:
            # ADESSO rimuovi le chiavi URL prima di aggiungere all'output
            clean_page = _remove_url_keys(matched_page)
            output.append(clean_page)

    return output