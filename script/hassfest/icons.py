"""Validate integration icon translation files."""

from __future__ import annotations

from typing import Any

import orjson
import voluptuous as vol
from voluptuous.humanize import humanize_error

import homeassistant.helpers.config_validation as cv

from .model import Config, Integration
from .translations import translation_key_validator


def icon_value_validator(value: Any) -> str:
    """Validate that the icon is a valid icon."""
    value = cv.string_with_no_html(value)
    if not value.startswith("mdi:"):
        raise vol.Invalid(
            "The icon needs to be a valid icon from Material Design Icons and start with `mdi:`"
        )
    return str(value)


def require_default_icon_validator(value: dict) -> dict:
    """Validate that a default icon is set."""
    if "_" not in value:
        raise vol.Invalid(
            "An entity component needs to have a default icon defined with `_`"
        )
    return value


def ensure_not_same_as_default(value: dict) -> dict:
    """Validate an icon isn't the same as its default icon."""
    for translation_key, section in value.items():
        if (default := section.get("default")) and (states := section.get("state")):
            for state, icon in states.items():
                if icon == default:
                    raise vol.Invalid(
                        f"The icon for state `{translation_key}.{state}` is the"
                        " same as the default icon and thus can be removed"
                    )

    return value


DATA_ENTRY_ICONS_SCHEMA = vol.Schema(
    {
        "step": {
            str: {
                "section": {
                    str: icon_value_validator,
                }
            }
        }
    }
)


def icon_schema(integration_type: str, no_entity_platform: bool) -> vol.Schema:
    """Create an icon schema."""

    state_validator = cv.schema_with_slug_keys(
        icon_value_validator,
        slug_validator=translation_key_validator,
    )

    def icon_schema_slug(marker: type[vol.Marker]) -> dict[vol.Marker, Any]:
        return {
            marker("default"): icon_value_validator,
            vol.Optional("state"): state_validator,
            vol.Optional("state_attributes"): vol.All(
                cv.schema_with_slug_keys(
                    {
                        marker("default"): icon_value_validator,
                        marker("state"): state_validator,
                    },
                    slug_validator=translation_key_validator,
                ),
                ensure_not_same_as_default,
            ),
        }

    schema = vol.Schema(
        {
            vol.Optional("config"): DATA_ENTRY_ICONS_SCHEMA,
            vol.Optional("issues"): vol.Schema(
                {str: {"fix_flow": DATA_ENTRY_ICONS_SCHEMA}}
            ),
            vol.Optional("options"): DATA_ENTRY_ICONS_SCHEMA,
            vol.Optional("services"): state_validator,
        }
    )

    if integration_type in ("entity", "helper", "system"):
        if integration_type != "entity" or no_entity_platform:
            field = vol.Optional("entity_component")
        else:
            field = vol.Required("entity_component")
        schema = schema.extend(
            {
                field: vol.All(
                    cv.schema_with_slug_keys(
                        icon_schema_slug(vol.Required),
                        slug_validator=vol.Any("_", cv.slug),
                    ),
                    require_default_icon_validator,
                    ensure_not_same_as_default,
                )
            }
        )
    if integration_type not in ("entity", "system"):
        schema = schema.extend(
            {
                vol.Optional("entity"): vol.All(
                    cv.schema_with_slug_keys(
                        cv.schema_with_slug_keys(
                            icon_schema_slug(vol.Optional),
                            slug_validator=translation_key_validator,
                        ),
                        slug_validator=cv.slug,
                    ),
                    ensure_not_same_as_default,
                )
            }
        )
    return schema


def validate_icon_file(config: Config, integration: Integration) -> None:
    """Validate icon file for integration."""
    icons_file = integration.path / "icons.json"
    if not icons_file.is_file():
        return

    name = str(icons_file.relative_to(integration.path))

    try:
        icons = orjson.loads(icons_file.read_text())
    except ValueError as err:
        integration.add_error("icons", f"Invalid JSON in {name}: {err}")
        return

    no_entity_platform = integration.domain in ("notify", "image_processing")

    schema = icon_schema(integration.integration_type, no_entity_platform)

    try:
        schema(icons)
    except vol.Invalid as err:
        integration.add_error("icons", f"Invalid {name}: {humanize_error(icons, err)}")


def validate(integrations: dict[str, Integration], config: Config) -> None:
    """Handle JSON files inside integrations."""
    for integration in integrations.values():
        validate_icon_file(config, integration)
