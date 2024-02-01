"""Helper script to update language list from the frontend source."""
import json
from pathlib import Path
import sys

import requests

from .hassfest.serializer import format_python_namespace

tag = sys.argv[1] if len(sys.argv) > 1 else "dev"

req = requests.get(
    f"https://raw.githubusercontent.com/home-assistant/frontend/{tag}/src/translations/translationMetadata.json"
)
data = json.loads(req.content)
languages = set(data.keys())

# Languages which can be used for entity IDs.
# Languages in the set are those which use a writing system based on the Latin
# script. Languages not in this set will instead base the entity ID on English.

# Note: Although vietnamese writing is based on the Latin script, it's too ambiguous
# after accents and diacritics have been removed by slugify
NATIVE_ENTITY_IDS = {
    "af",  # Afrikaans
    "bs",  # Bosanski
    "ca",  # Català
    "cs",  # Čeština
    "cy",  # Cymraeg
    "da",  # Dansk
    "de",  # Deutsch
    "en",  # English
    "en-GB",  # English (GB)
    "eo",  # Esperanto
    "es",  # Español
    "es-419",  # Español (Latin America)
    "et",  # Eesti
    "eu",  # Euskara
    "fi",  # Suomi
    "fr",  # Français
    "fy",  # Frysk
    "gl",  # Galego
    "gsw",  # Schwiizerdütsch
    "hr",  # Hrvatski
    "hu",  # Magyar
    "id",  # Indonesia
    "is",  # Íslenska
    "it",  # Italiano
    "ka",  # Kartuli
    "lb",  # Lëtzebuergesch
    "lt",  # Lietuvių
    "lv",  # Latviešu
    "nb",  # Nederlands
    "nl",  # Norsk Bokmål
    "nn",  # Norsk Nynorsk"
    "pl",  # Polski
    "pt",  # Português
    "pt-BR",  # Português (BR)
    "ro",  # Română
    "sk",  # Slovenčina
    "sl",  # Slovenščina
    "sr-Latn",  # Srpski
    "sv",  # Svenska
    "tr",  # Türkçe
}

Path("homeassistant/generated/languages.py").write_text(
    format_python_namespace(
        {
            "DEFAULT_LANGUAGE": "en",
            "LANGUAGES": languages,
            "NATIVE_ENTITY_IDS": NATIVE_ENTITY_IDS,
        },
        generator="script.languages [frontend_tag]",
    )
)
