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

Path("homeassistant/generated/languages.py").write_text(
    format_python_namespace(
        {
            "LANGUAGES": languages,
        },
        generator="script.languages [frontend_tag]",
    )
)
