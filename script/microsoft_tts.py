"""Helper script to update supported languages and regions for Microsoft text-to-speech (TTS)."""

from pathlib import Path

from hassfest.serializer import format_python_namespace
from lxml import html
import requests

LANGUAGES_URL = "https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support"
LANGUAGES_XPATH_QUERY = "//section[@data-tab='tts']/table[1]/tbody/tr/td[1]/code/text()"

REGIONS_URL = (
    "https://learn.microsoft.com/en-us/azure/ai-services/speech-service/regions"
)
REGIONS_XPATH_QUERY = (
    "//section[@data-tab='geographies']/table[1]/tbody/tr/td[3]/code/text()"
)


def query_documentation(url: str, xpath_query: str) -> set[str]:
    """Return the lowercase results of an XPath query on a documentation page."""
    req = requests.get(url)
    req.raise_for_status()
    tree = html.fromstring(req.content)
    return {s.lower() for s in tree.xpath(xpath_query)}


Path("homeassistant/generated/microsoft_tts.py").write_text(
    format_python_namespace(
        {
            "SUPPORTED_LANGUAGES": query_documentation(
                LANGUAGES_URL, LANGUAGES_XPATH_QUERY
            ),
            "SUPPORTED_REGIONS": query_documentation(REGIONS_URL, REGIONS_XPATH_QUERY),
        },
        generator="script.microsoft_tts",
    )
)
