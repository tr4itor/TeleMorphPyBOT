import re
import logging
from functools import lru_cache
from config_manager import ConfigManager

logger = logging.getLogger(__name__)

_config = ConfigManager()

@lru_cache(maxsize=1)
def _get_signature_pattern(version=0):
    stopwords = _config.get_stopwords()
    if not stopwords:
        return re.compile(r'(?!x)x')  
    escaped = [re.escape(w) for w in stopwords]
    pattern = r'(?i)\b(?:' + '|'.join(escaped) + r')\b'
    return re.compile(pattern)

def get_signature_pattern():
    return _get_signature_pattern(version=0)

def clear_cache():
    _get_signature_pattern.cache_clear()
    logger.info("Stopword regular expression cache cleared")

def remove_signatures(text: str) -> str:
    if not text or not text.strip():
        return text

    stopwords = _config.get_stopwords()
    if not stopwords:
        return text

    pattern = get_signature_pattern()
    lines = text.splitlines()
    while lines and not lines[-1].strip():
        lines.pop()

    removed_count = 0
    while lines and pattern.search(lines[-1]):
        logger.debug(f"Row deleted: {lines[-1]!r}")
        lines.pop()
        removed_count += 1
        while lines and not lines[-1].strip():
            lines.pop()

    if removed_count:
        logger.info(f"Filter removed {removed_count} rows")
    return '\n'.join(lines)
