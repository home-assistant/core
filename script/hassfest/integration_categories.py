"""Generate the integration_categories.json file."""

import json
from pathlib import Path

from .model import Config, Integration

PATH = "homeassistant/generated/integration_categories.json"


def _generate(integration_path: Path) -> str:
    """Generate the integration categories data from the strings and icons."""
    strings = json.loads((integration_path / "strings.json").read_text())
    icons = json.loads((integration_path / "icons.json").read_text())
    category_strings = strings["integration_category"]
    category_icons = icons.get("integration_category", {})

    # A missing icon becomes None here, the icons plugin reports it as an error.
    categories = []
    for category, details in sorted(category_strings.items()):
        icon_details = category_icons.get(category, {})
        subcategory_icons = icon_details.get("subcategory", {})

        subcategories = [
            {
                "slug": subcategory,
                "name": subcategory_details["name"],
                "icon": subcategory_icons.get(subcategory, {}).get("default"),
            }
            for subcategory, subcategory_details in sorted(
                details.get("subcategory", {}).items()
            )
        ]

        categories.append(
            {
                "slug": category,
                "name": details["name"],
                "description": details["description"],
                "icon": icon_details.get("default"),
                "subcategories": subcategories,
            }
        )

    return json.dumps(categories, indent=2)


def validate(integrations: dict[str, Integration], config: Config) -> None:
    """Validate integration_categories.json."""
    path = config.root / PATH
    config.cache["integration_categories"] = content = _generate(
        integrations["homeassistant"].path
    )

    if not path.is_file() or path.read_text() != content + "\n":
        config.add_error(
            "integration_categories",
            "File integration_categories.json is not up to date. "
            "Run python3 -m script.hassfest",
            fixable=True,
        )


def generate(integrations: dict[str, Integration], config: Config) -> None:
    """Generate integration_categories.json."""
    path = config.root / PATH
    path.write_text(f"{config.cache['integration_categories']}\n")
