"""Validate integration quality scale files."""

from __future__ import annotations

import voluptuous as vol
from voluptuous.humanize import humanize_error

from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.yaml import load_yaml_dict

from .model import Config, Integration

SCHEMA = vol.Schema(
    {
        vol.Required("rules"): vol.Schema(
            {
                str: vol.Any(
                    vol.In(["todo", "done"]),
                    vol.Schema(
                        {
                            vol.Required("status"): vol.In(
                                ["todo", "done", "exempted"]
                            ),
                            vol.Optional("comment"): str,
                        }
                    ),
                )
            }
        )
    }
)


def validate_iqs_file(config: Config, integration: Integration) -> None:
    """Validate quality scale file for integration."""
    iqs_file = integration.path / "quality_scale.yaml"
    if not iqs_file.is_file():
        return

    name = str(iqs_file)

    try:
        data = load_yaml_dict(name)
    except HomeAssistantError:
        integration.add_error("quality_scale", "Invalid quality_scale.yaml")
        return

    try:
        SCHEMA(data)
    except vol.Invalid as err:
        integration.add_error(
            "quality_scale", f"Invalid {name}: {humanize_error(data, err)}"
        )


def validate(integrations: dict[str, Integration], config: Config) -> None:
    """Handle YAML files inside integrations."""
    for integration in integrations.values():
        validate_iqs_file(config, integration)
