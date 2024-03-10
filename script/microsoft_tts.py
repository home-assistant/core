"""Helper script to update supported languages for Microsoft text-to-speech (TTS)."""

from pathlib import Path

from lxml import html
import requests

from .hassfest.serializer import format_python_namespace

URL = "https://docs.microsoft.com/en-us/azure/cognitive-services/speech-service/language-support"
XPATH_QUERY = "//section[@data-tab='tts']/table[1]/tbody/tr/td[1]/code/text()"

req = requests.get(URL)
req.raise_for_status()
tree = html.fromstring(req.content)
supported_languages_raw = tree.xpath(XPATH_QUERY)
supported_languages = {s.lower() for s in supported_languages_raw}

Path("homeassistant/generated/microsoft_tts.py").write_text(
    format_python_namespace(
        {
            "SUPPORTED_LANGUAGES": supported_languages,
        },
        generator="script.microsoft_tts",
    )
)
