"""Generate the integration_categories.json file."""

import json
from pathlib import Path

from .icons import integration_category_keys
from .model import Config, Integration

PATH = "homeassistant/generated/integration_categories.json"
MANIFEST_SCHEMA_PATH = "script/json_schemas/manifest_schema.json"


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


def _validate_manifest_schema(integration_path: Path, config: Config) -> None:
    """Validate the manifest JSON schema lists every category."""
    strings = json.loads((integration_path / "strings.json").read_text())
    categories = sorted(
        integration_category_keys(strings.get("integration_category", {}))
    )
    schema = json.loads((config.root / MANIFEST_SCHEMA_PATH).read_text())
    schema_categories = schema["else"]["properties"]["categories"]["items"]["enum"]

    if schema_categories != categories:
        config.add_error(
            "integration_categories",
            f"The categories in {MANIFEST_SCHEMA_PATH} are not up to date, "
            f"expected: {categories}",
        )


def validate(integrations: dict[str, Integration], config: Config) -> None:
    """Validate integration_categories.json."""
    path = config.root / PATH
    integration = integrations["homeassistant"]

    # The json, translations and icons plugins report invalid strings and icons,
    # and generating from them would crash.
    if any(not error.fixable for error in integration.errors):
        return

    config.cache["integration_categories"] = content = _generate(integration.path)
    _validate_manifest_schema(integration.path, config)

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
