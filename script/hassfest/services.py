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
from homeassistant.util.yaml import load_yaml_dict

from .model import Config, Integration


def exists(value: Any) -> Any:
    """Check if value exists."""
    if value is None:
        raise vol.Invalid("Value cannot be None")
    return value


def unique_field_validator(fields: Any) -> Any:
    """Validate the inputs don't have duplicate keys under different sections."""
    all_fields = set()
    for key, value in fields.items():
        if value and "fields" in value:
            for key in value["fields"]:
                if key in all_fields:
                    raise vol.Invalid(f"Duplicate use of field {key} in service.")
                all_fields.add(key)
        else:
            if key in all_fields:
                raise vol.Invalid(f"Duplicate use of field {key} in service.")
            all_fields.add(key)

    return fields


CORE_INTEGRATION_FIELD_SCHEMA = vol.Schema(
    {
        vol.Optional("example"): exists,
        vol.Optional("default"): exists,
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

CORE_INTEGRATION_SECTION_SCHEMA = vol.Schema(
    {
        vol.Optional("collapsed"): bool,
        vol.Required("fields"): vol.Schema({str: CORE_INTEGRATION_FIELD_SCHEMA}),
    }
)

CUSTOM_INTEGRATION_FIELD_SCHEMA = CORE_INTEGRATION_FIELD_SCHEMA.extend(
    {
        vol.Optional("description"): str,
        vol.Optional("name"): str,
    }
)

CUSTOM_INTEGRATION_SECTION_SCHEMA = vol.Schema(
    {
        vol.Optional("description"): str,
        vol.Optional("name"): str,
        vol.Optional("collapsed"): bool,
        vol.Required("fields"): vol.Schema({str: CUSTOM_INTEGRATION_FIELD_SCHEMA}),
    }
)


CORE_INTEGRATION_SERVICE_SCHEMA = vol.Any(
    vol.Schema(
        {
            vol.Optional("target"): vol.Any(
                selector.TargetSelector.CONFIG_SCHEMA, None
            ),
            vol.Optional("fields"): vol.All(
                vol.Schema(
                    {
                        str: vol.Any(
                            CORE_INTEGRATION_FIELD_SCHEMA,
                            CORE_INTEGRATION_SECTION_SCHEMA,
                        )
                    }
                ),
                unique_field_validator,
            ),
        }
    ),
    None,
)

CUSTOM_INTEGRATION_SERVICE_SCHEMA = vol.Any(
    vol.Schema(
        {
            vol.Optional("description"): str,
            vol.Optional("name"): str,
            vol.Optional("target"): vol.Any(
                selector.TargetSelector.CONFIG_SCHEMA, None
            ),
            vol.Optional("fields"): vol.All(
                vol.Schema(
                    {
                        str: vol.Any(
                            CUSTOM_INTEGRATION_FIELD_SCHEMA,
                            CUSTOM_INTEGRATION_SECTION_SCHEMA,
                        )
                    }
                ),
                unique_field_validator,
            ),
        }
    ),
    None,
)

CORE_INTEGRATION_SERVICES_SCHEMA = vol.Schema(
    {
        vol.Remove(vol.All(str, service.starts_with_dot)): object,
        cv.slug: CORE_INTEGRATION_SERVICE_SCHEMA,
    }
)
CUSTOM_INTEGRATION_SERVICES_SCHEMA = vol.Schema(
    {cv.slug: CUSTOM_INTEGRATION_SERVICE_SCHEMA}
)

VALIDATE_AS_CUSTOM_INTEGRATION = {
    # Adding translations would be a breaking change
    "foursquare",
}


def grep_dir(path: pathlib.Path, glob_pattern: str, search_pattern: str) -> bool:
    """Recursively go through a dir and it's children and find the regex."""
    pattern = re.compile(search_pattern)

    for fil in path.glob(glob_pattern):
        if not fil.is_file():
            continue

        if pattern.search(fil.read_text()):
            return True

    return False


def validate_services(config: Config, integration: Integration) -> None:  # noqa: C901
    """Validate services."""
    try:
        data = load_yaml_dict(str(integration.path / "services.yaml"))
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
        integration.add_error("services", "Invalid services.yaml")
        return

    try:
        if (
            integration.core
            and integration.domain not in VALIDATE_AS_CUSTOM_INTEGRATION
        ):
            services = CORE_INTEGRATION_SERVICES_SCHEMA(data)
        else:
            services = CUSTOM_INTEGRATION_SERVICES_SCHEMA(data)
    except vol.Invalid as err:
        integration.add_error(
            "services", f"Invalid services.yaml: {humanize_error(data, err)}"
        )
        return

    icons_file = integration.path / "icons.json"
    icons = {}
    if icons_file.is_file():
        with contextlib.suppress(ValueError):
            icons = json.loads(icons_file.read_text())
    service_icons = icons.get("services", {})

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

    error_msg_suffix = "in the translations file"
    if not integration.core:
        error_msg_suffix = f"and is not {error_msg_suffix}"

    # For each service in the integration:
    # 1. Check if the service description is set, if not,
    #    check if it's in the strings file else add an error.
    # 2. Check if the service has an icon set in icons.json.
    #    raise an error if not.,
    for service_name, service_schema in services.items():
        if integration.core and service_name not in service_icons:
            # This is enforced for Core integrations only
            integration.add_error(
                "services",
                f"Service {service_name} has no icon in icons.json.",
            )
        if service_schema is None:
            continue
        if "name" not in service_schema:
            try:
                strings["services"][service_name]["name"]
            except KeyError:
                integration.add_error(
                    "services",
                    f"Service {service_name} has no name {error_msg_suffix}",
                )

        if "description" not in service_schema:
            try:
                strings["services"][service_name]["description"]
            except KeyError:
                integration.add_error(
                    "services",
                    f"Service {service_name} has no description {error_msg_suffix}",
                )

        # The same check is done for the description in each of the fields of the
        # service schema.
        for field_name, field_schema in service_schema.get("fields", {}).items():
            if "fields" in field_schema:
                # This is a section
                continue
            if "name" not in field_schema:
                try:
                    strings["services"][service_name]["fields"][field_name]["name"]
                except KeyError:
                    integration.add_error(
                        "services",
                        f"Service {service_name} has a field {field_name} with no name {error_msg_suffix}",
                    )

            if "description" not in field_schema:
                try:
                    strings["services"][service_name]["fields"][field_name][
                        "description"
                    ]
                except KeyError:
                    integration.add_error(
                        "services",
                        f"Service {service_name} has a field {field_name} with no description {error_msg_suffix}",
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

        # The same check is done for the description in each of the sections of the
        # service schema.
        for section_name, section_schema in service_schema.get("fields", {}).items():
            if "fields" not in section_schema:
                # This is not a section
                continue
            try:
                strings["services"][service_name]["sections"][section_name]["name"]
            except KeyError:
                integration.add_error(
                    "services",
                    f"Service {service_name} has a section {section_name} with no name {error_msg_suffix}",
                )


def validate(integrations: dict[str, Integration], config: Config) -> None:
    """Handle dependencies for integrations."""
    # check services.yaml is cool
    for integration in integrations.values():
        validate_services(config, integration)
