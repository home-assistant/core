"""Validate integration quality scale files."""

from __future__ import annotations

import orjson
import voluptuous as vol
from voluptuous.humanize import humanize_error

import homeassistant.helpers.config_validation as cv

from .model import Config, Integration

SCHEMA = vol.Schema(
    {
        str: vol.Schema(
            {
                vol.Required("implemented"): cv.boolean,
                vol.Optional("exempt_reason"): cv.string,
            }
        )
    }
)


def validate_iqs_file(config: Config, integration: Integration) -> None:
    """Validate iqs file for integration."""
    iqs_file = integration.path / "iqs.json"
    if not iqs_file.is_file():
        return

    name = str(iqs_file.relative_to(integration.path))

    try:
        icons = orjson.loads(iqs_file.read_text())
    except ValueError as err:
        integration.add_error("iqs", f"Invalid JSON in {name}: {err}")
        return

    try:
        SCHEMA(icons)
    except vol.Invalid as err:
        integration.add_error("iqs", f"Invalid {name}: {humanize_error(icons, err)}")


def validate(integrations: dict[str, Integration], config: Config) -> None:
    """Handle JSON files inside integrations."""
    for integration in integrations.values():
        validate_iqs_file(config, integration)
