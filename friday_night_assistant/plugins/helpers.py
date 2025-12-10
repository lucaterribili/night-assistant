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


def _extract_path_from_page(page: Dict[str, Any]) -> Optional[str]:
    """Estrae il path pulito (senza query) da una voce Matomo.

    Cerca le chiavi comuni: 'url', 'label', 'pageUrl'. Se il valore è un URL
    completo, viene parsato e ritorna solo il path.
    """
    raw = None
    for key in ("url", "label", "pageUrl"):
        raw = page.get(key)
        if raw:
            break
    if not raw:
        return None

    try:
        parsed = urlparse(raw)
        path = parsed.path or raw
    except Exception:
        path = raw

    # normalizza: rimuovi query/fragment già fatto da urlparse; rimuovi trailing slash
    if path.endswith("/") and path != "/":
        path = path.rstrip("/")

    # rimuovi eventuale leading slash per matching coerente
    return path.lstrip("/")


def normalize_matomo_response(pages: Any, patterns: Optional[List[Tuple[re.Pattern, str]]] = None) -> List[Dict[str, Any]]:
    """Normalizza e filtra una risposta Matomo.

    - Trasforma input dict/list/elemento singolo in lista di dict
    - Estrae il path da ogni voce e filtra usando i `patterns`
    - Aggiunge il campo 'type' con valore 'blog' o 'tutorial'
    - Aggiunge opzionalmente 'slug' se catturato dal regex

    Args:
        pages: risposta grezza dall'API Matomo
        patterns: lista di tuple (compiled_regex, type). Se None usa PATTERNS

    Returns:
        lista di dict (voci Matomo annotate) contenente solo le pagine corrispondenti
        ai pattern richiesti
    """
    patterns = patterns or PATTERNS

    # normalizza a lista
    if isinstance(pages, dict):
        pages = pages.get("result", list(pages.values()))
    if not isinstance(pages, list):
        pages = [pages]

    out: List[Dict[str, Any]] = []

    for page in pages:
        if not isinstance(page, dict):
            logger.debug("Skipping non-dict page item: %s", type(page))
            continue

        path = _extract_path_from_page(page)
        if not path:
            continue

        matched = False
        for regex, ptype in patterns:
            m = regex.match(path)
            if not m:
                continue

            # annotate copy of page
            new_page = page.copy()
            new_page["type"] = ptype
            # aggiungi slug se disponibile
            try:
                if "slug" in m.groupdict() and m.group("slug"):
                    new_page["slug"] = m.group("slug")
            except Exception:
                # non critico
                logger.debug("Failed to extract slug for path %s with pattern %s", path, regex.pattern)

            out.append(new_page)
            matched = True
            break

        if not matched:
            logger.debug("Page did not match any pattern: %s", path)

    return out