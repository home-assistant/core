"""Generate the integration_connectivity.json file."""

import json
from pathlib import Path

from .model import Config, Integration

PATH = "homeassistant/generated/integration_connectivity.json"


def _generate(integration_path: Path) -> str:
    """Generate the connectivity data from the strings and icons."""
    strings = json.loads((integration_path / "strings.json").read_text())
    icons = json.loads((integration_path / "icons.json").read_text())
    connectivity_strings = strings.get("integration_connectivity", {})
    connectivity_icons = icons.get("integration_connectivity", {})

    connectivity = [
        {
            "slug": slug,
            "name": details["name"],
            "description": details["description"],
            "icon": connectivity_icons[slug]["default"],
        }
        for slug, details in sorted(connectivity_strings.items())
    ]

    return json.dumps(connectivity, indent=2)


def validate(integrations: dict[str, Integration], config: Config) -> None:
    """Validate integration_connectivity.json."""
    path = config.root / PATH
    integration = integrations["homeassistant"]

    # The json, translations and icons plugins report invalid strings and icons,
    # and generating from them would crash.
    if any(not error.fixable for error in integration.errors):
        return

    config.cache["integration_connectivity"] = content = _generate(integration.path)

    if not path.is_file() or path.read_text() != content + "\n":
        config.add_error(
            "integration_connectivity",
            "File integration_connectivity.json is not up to date. "
            "Run python3 -m script.hassfest",
            fixable=True,
        )


def generate(integrations: dict[str, Integration], config: Config) -> None:
    """Generate integration_connectivity.json."""
    path = config.root / PATH
    path.write_text(f"{config.cache['integration_connectivity']}\n")
