"""Generate the integration_categories.json and integration_categories.py files."""

import json
from pathlib import Path

from hassfest.model import Config, Integration
from hassfest.serializer import format_python_namespace

PATH = "homeassistant/generated/integration_categories.json"
PYTHON_PATH = "homeassistant/generated/integration_categories.py"


def _generate(integration_path: Path) -> str:
    """Generate the integration categories data from the strings and icons."""
    strings = json.loads((integration_path / "strings.json").read_text())
    icons = json.loads((integration_path / "icons.json").read_text())
    category_strings = strings.get("integration_category", {})
    category_icons = icons.get("integration_category", {})

    categories = []
    for category, details in sorted(category_strings.items()):
        icon_details = category_icons[category]

        subcategories = [
            {
                "slug": subcategory,
                "name": subcategory_details["name"],
                "icon": icon_details["subcategory"][subcategory]["default"],
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
                "icon": icon_details["default"],
                "subcategories": subcategories,
            }
        )

    return json.dumps(categories, indent=2)


def _generate_python(categories_json: str) -> str:
    """Generate the slugs of the top-level categories, for code that needs them."""
    return format_python_namespace(
        {
            "INTEGRATION_CATEGORIES": [
                category["slug"] for category in json.loads(categories_json)
            ]
        }
    )


def validate(integrations: dict[str, Integration], config: Config) -> None:
    """Validate integration_categories.json and integration_categories.py."""
    path = config.root / PATH
    python_path = config.root / PYTHON_PATH
    integration = integrations["homeassistant"]

    # The json, translations and icons plugins report invalid strings and icons,
    # and generating from them would crash.
    if any(not error.fixable for error in integration.errors):
        return

    config.cache["integration_categories"] = content = _generate(integration.path)

    if not path.is_file() or path.read_text() != content + "\n":
        config.add_error(
            "integration_categories",
            "File integration_categories.json is not up to date. "
            "Run python3 -m script.hassfest",
            fixable=True,
        )

    config.cache["integration_categories_python"] = python_content = _generate_python(
        content
    )

    if not python_path.is_file() or python_path.read_text() != python_content:
        config.add_error(
            "integration_categories",
            "File integration_categories.py is not up to date. "
            "Run python3 -m script.hassfest",
            fixable=True,
        )


def generate(integrations: dict[str, Integration], config: Config) -> None:
    """Generate integration_categories.json and integration_categories.py."""
    path = config.root / PATH
    path.write_text(f"{config.cache['integration_categories']}\n")
    python_path = config.root / PYTHON_PATH
    python_path.write_text(config.cache["integration_categories_python"])
