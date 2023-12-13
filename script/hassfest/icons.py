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


def icon_schema(integration_type: str) -> vol.Schema:
    """Create a icon schema."""

    state_validator = cv.schema_with_slug_keys(
        icon_value_validator,
        slug_validator=translation_key_validator,
    )

    base_schema = vol.Schema(
        {
            vol.Optional("services"): state_validator,
        }
    )

    if integration_type == "entity":
        return base_schema.extend(
            {
                vol.Required("entity_component"): cv.schema_with_slug_keys(
                    {
                        vol.Required("default"): icon_value_validator,
                        vol.Optional("state"): state_validator,
                        vol.Optional("state_attributes"): cv.schema_with_slug_keys(
                            {
                                vol.Required("default"): icon_value_validator,
                                vol.Required("state"): state_validator,
                            },
                            slug_validator=translation_key_validator,
                        ),
                    },
                    slug_validator=vol.Any("_", cv.slug),
                ),
            }
        )
    return base_schema.extend(
        {
            vol.Required("entity"): cv.schema_with_slug_keys(
                cv.schema_with_slug_keys(
                    {
                        vol.Optional("default"): icon_value_validator,
                        vol.Optional("state"): state_validator,
                        vol.Optional("state_attributes"): cv.schema_with_slug_keys(
                            {
                                vol.Optional("default"): icon_value_validator,
                                vol.Optional("state"): state_validator,
                            },
                            slug_validator=translation_key_validator,
                        ),
                    },
                    slug_validator=translation_key_validator,
                ),
                slug_validator=cv.slug,
            ),
        }
    )


def validate_icon_file(config: Config, integration: Integration) -> None:  # noqa: C901
    """Validate icon file for integration."""
    icons_file = integration.path / "icons.json"
    if not icons_file.is_file():
        return

    schema = icon_schema(integration.integration_type)
    name = str(icons_file.relative_to(integration.path))

    try:
        icons = orjson.loads(icons_file.read_text())
    except ValueError as err:
        integration.add_error("icons", f"Invalid JSON in {name}: {err}")
        return

    try:
        schema(icons)
    except vol.Invalid as err:
        integration.add_error("icons", f"Invalid {name}: {humanize_error(icons, err)}")


def validate(integrations: dict[str, Integration], config: Config) -> None:
    """Handle JSON files inside integrations."""
    for integration in integrations.values():
        validate_icon_file(config, integration)
