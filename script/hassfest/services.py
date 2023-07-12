"""Validate dependencies."""
from __future__ import annotations

import contextlib
import json
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
        vol.Optional("description"): str,
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

SERVICE_SCHEMA = vol.Any(
    vol.Schema(
        {
            vol.Optional("description"): str,
            vol.Optional("name"): str,
            vol.Optional("target"): vol.Any(
                selector.TargetSelector.CONFIG_SCHEMA, None
            ),
            vol.Optional("fields"): vol.Schema({str: FIELD_SCHEMA}),
        }
    ),
    None,
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


def validate_services(config: Config, integration: Integration) -> None:
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
        services = SERVICES_SCHEMA(data)
    except vol.Invalid as err:
        integration.add_error(
            "services", f"Invalid services.yaml: {humanize_error(data, err)}"
        )
        return

    # Try loading translation strings
    if integration.core:
        strings_file = integration.path / "strings.json"
    else:
        # For custom integrations, use the en.json file
        strings_file = integration.path / "translations/en.json"

    strings = {}
    if strings_file.is_file():
        with contextlib.suppress(ValueError):
            strings = json.loads(strings_file.read_text())

    # For each service in the integration, check if the description if set,
    # if not, check if it's in the strings file. If not, add an error.
    for service_name, service_schema in services.items():
        if service_schema is None:
            continue
        if "name" not in service_schema:
            try:
                strings["services"][service_name]["name"]
            except KeyError:
                integration.add_error(
                    "services",
                    f"Service {service_name} has no name and is not in the translations file",
                )

        if "description" not in service_schema:
            try:
                strings["services"][service_name]["description"]
            except KeyError:
                integration.add_error(
                    "services",
                    f"Service {service_name} has no description and is not in the translations file",
                )

        # The same check is done for the description in each of the fields of the
        # service schema.
        for field_name, field_schema in service_schema.get("fields", {}).items():
            if "description" not in field_schema:
                try:
                    strings["services"][service_name]["fields"][field_name][
                        "description"
                    ]
                except KeyError:
                    integration.add_error(
                        "services",
                        f"Service {service_name} has a field {field_name} with no description and is not in the translations file",
                    )

            if "selector" in field_schema:
                with contextlib.suppress(KeyError):
                    translation_key = field_schema["selector"]["select"][
                        "translation_key"
                    ]
                    try:
                        strings["selector"][translation_key]
                    except KeyError:
                        integration.add_error(
                            "services",
                            f"Service {service_name} has a field {field_name} with a selector with a translation key {translation_key} that is not in the translations file",
                        )


def validate(integrations: dict[str, Integration], config: Config) -> None:
    """Handle dependencies for integrations."""
    # check services.yaml is cool
    for integration in integrations.values():
        validate_services(config, integration)
