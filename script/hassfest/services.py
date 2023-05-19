"""Validate dependencies."""
from __future__ import annotations

import pathlib
import re
from typing import Any

import voluptuous as vol
from voluptuous.humanize import humanize_error

from homeassistant.const import CONF_SELECTOR
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, selector, service
from homeassistant.util.yaml import load_yaml

from .model import Config, Integration


def exists(value: Any) -> Any:
    """Check if value exists."""
    if value is None:
        raise vol.Invalid("Value cannot be None")
    return value


FIELD_SCHEMA = vol.Schema(
    {
        vol.Required("description"): str,
        vol.Optional("name"): str,
        vol.Optional("example"): exists,
        vol.Optional("default"): exists,
        vol.Optional("values"): exists,
        vol.Optional("required"): bool,
        vol.Optional("advanced"): bool,
        vol.Optional(CONF_SELECTOR): selector.validate_selector,
        vol.Optional("filter"): {
            vol.Exclusive("attribute", "field_filter"): {
                vol.Required(str): [vol.All(str, service.validate_attribute_option)],
            },
            vol.Exclusive("supported_features", "field_filter"): [
                vol.All(str, service.validate_supported_feature)
            ],
        },
    }
)

SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required("description"): str,
        vol.Optional("name"): str,
        vol.Optional("target"): vol.Any(selector.TargetSelector.CONFIG_SCHEMA, None),
        vol.Optional("fields"): vol.Schema({str: FIELD_SCHEMA}),
    }
)

SERVICES_SCHEMA = vol.Schema({cv.slug: SERVICE_SCHEMA})


def grep_dir(path: pathlib.Path, glob_pattern: str, search_pattern: str) -> bool:
    """Recursively go through a dir and it's children and find the regex."""
    pattern = re.compile(search_pattern)

    for fil in path.glob(glob_pattern):
        if not fil.is_file():
            continue

        if pattern.search(fil.read_text()):
            return True

    return False


def validate_services(integration: Integration) -> None:
    """Validate services."""
    try:
        data = load_yaml(str(integration.path / "services.yaml"))
    except FileNotFoundError:
        # Find if integration uses services
        has_services = grep_dir(
            integration.path,
            "**/*.py",
            r"(hass\.services\.(register|async_register))|async_register_entity_service|async_register_admin_service",
        )

        if has_services:
            integration.add_error(
                "services", "Registers services but has no services.yaml"
            )
        return
    except HomeAssistantError:
        integration.add_error("services", "Unable to load services.yaml")
        return

    try:
        SERVICES_SCHEMA(data)
    except vol.Invalid as err:
        integration.add_error(
            "services", f"Invalid services.yaml: {humanize_error(data, err)}"
        )


def validate(integrations: dict[str, Integration], config: Config) -> None:
    """Handle dependencies for integrations."""
    # check services.yaml is cool
    for integration in integrations.values():
        validate_services(integration)
