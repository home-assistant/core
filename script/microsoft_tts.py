"""Helper script to update supported languages for Microsoft text-to-speech (TTS)."""
from pathlib import Path

from lxml import html
import requests

from .hassfest.serializer import format_python_namespace

URL = "https://docs.microsoft.com/en-us/azure/cognitive-services/speech-service/language-support"
XPATH_QUERY = "//section[@data-tab='tts']/table[1]/tbody/tr/td[3]/code/text()"

req = requests.get(URL)
req.raise_for_status()
tree = html.fromstring(req.content)
supported_languages_raw = tree.xpath(XPATH_QUERY)
default_languages_types = {}
for s in supported_languages_raw:
    key = "-".join(s.lower().split("-")[:-1])
    if key in default_languages_types:
        continue
    default_languages_types[key] = s.lower().split("-")[-1]


Path("homeassistant/generated/microsoft_tts.py").write_text(
    format_python_namespace(
        {
            "DEFAULT_LANGUAGES_TYPES": default_languages_types,
        },
        generator="script.microsoft_tts",
    )
)
