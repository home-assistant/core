"""Validate conditions."""

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
from homeassistant.helpers import condition, config_validation as cv, selector
from homeassistant.util.yaml import load_yaml_dict

from .model import Config, Integration


def exists(value: Any) -> Any:
    """Check if value exists."""
    if value is None:
        raise vol.Invalid("Value cannot be None")
    return value


FIELD_SCHEMA = vol.Schema(
    {
        vol.Optional("example"): exists,
        vol.Optional("default"): exists,
        vol.Optional("required"): bool,
        vol.Optional(CONF_SELECTOR): selector.validate_selector,
    }
)

CONDITION_SCHEMA = vol.Any(
    vol.Schema(
        {
            vol.Optional("target"): selector.TargetSelector.CONFIG_SCHEMA,
            vol.Optional("fields"): vol.Schema({str: FIELD_SCHEMA}),
        }
    ),
    None,
)

CONDITIONS_SCHEMA = vol.Schema(
    {
        vol.Remove(vol.All(str, condition.starts_with_dot)): object,
        cv.underscore_slug: CONDITION_SCHEMA,
    }
)

NON_MIGRATED_INTEGRATIONS = {
    "device_automation",
    "sun",
    "zone",
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


def validate_conditions(config: Config, integration: Integration) -> None:  # noqa: C901
    """Validate conditions."""
    try:
        data = load_yaml_dict(str(integration.path / "conditions.yaml"))
    except FileNotFoundError:
        # Find if integration uses conditions
        has_conditions = grep_dir(
            integration.path,
            "**/condition.py",
            r"async_get_conditions",
        )

        if has_conditions and integration.domain not in NON_MIGRATED_INTEGRATIONS:
            integration.add_error(
                "conditions", "Registers conditions but has no conditions.yaml"
            )
        return
    except HomeAssistantError:
        integration.add_error("conditions", "Invalid conditions.yaml")
        return

    try:
        conditions = CONDITIONS_SCHEMA(data)
    except vol.Invalid as err:
        integration.add_error(
            "conditions", f"Invalid conditions.yaml: {humanize_error(data, err)}"
        )
        return

    icons_file = integration.path / "icons.json"
    icons = {}
    if icons_file.is_file():
        with contextlib.suppress(ValueError):
            icons = json.loads(icons_file.read_text())
    condition_icons = icons.get("conditions", {})

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

    # For each condition in the integration:
    # 1. Check if the condition description is set, if not,
    #    check if it's in the strings file else add an error.
    # 2. Check if the condition has an icon set in icons.json.
    #    raise an error if not.,
    for condition_name, condition_schema in conditions.items():
        if integration.core and condition_name not in condition_icons:
            # This is enforced for Core integrations only
            integration.add_error(
                "conditions",
                f"Condition {condition_name} has no icon in icons.json.",
            )
        if condition_schema is None:
            continue
        if "name" not in condition_schema and integration.core:
            try:
                strings["conditions"][condition_name]["name"]
            except KeyError:
                integration.add_error(
                    "conditions",
                    f"Condition {condition_name} has no name {error_msg_suffix}",
                )

        if "description" not in condition_schema and integration.core:
            try:
                strings["conditions"][condition_name]["description"]
            except KeyError:
                integration.add_error(
                    "conditions",
                    f"Condition {condition_name} has no description {error_msg_suffix}",
                )

        # The same check is done for the description in each of the fields of the
        # condition schema.
        for field_name, field_schema in condition_schema.get("fields", {}).items():
            if "fields" in field_schema:
                # This is a section
                continue
            if "name" not in field_schema and integration.core:
                try:
                    strings["conditions"][condition_name]["fields"][field_name]["name"]
                except KeyError:
                    integration.add_error(
                        "conditions",
                        (
                            f"Condition {condition_name} has a field {field_name} with no "
                            f"name {error_msg_suffix}"
                        ),
                    )

            if "description" not in field_schema and integration.core:
                try:
                    strings["conditions"][condition_name]["fields"][field_name][
                        "description"
                    ]
                except KeyError:
                    integration.add_error(
                        "conditions",
                        (
                            f"Condition {condition_name} has a field {field_name} with no "
                            f"description {error_msg_suffix}"
                        ),
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
                            "conditions",
                            f"Condition {condition_name} has a field {field_name} with a selector with a translation key {translation_key} that is not in the translations file",
                        )

        # The same check is done for the description in each of the sections of the
        # condition schema.
        for section_name, section_schema in condition_schema.get("fields", {}).items():
            if "fields" not in section_schema:
                # This is not a section
                continue
            if "name" not in section_schema and integration.core:
                try:
                    strings["conditions"][condition_name]["sections"][section_name][
                        "name"
                    ]
                except KeyError:
                    integration.add_error(
                        "conditions",
                        f"Condition {condition_name} has a section {section_name} with no name {error_msg_suffix}",
                    )


def validate(integrations: dict[str, Integration], config: Config) -> None:
    """Handle dependencies for integrations."""
    # check conditions.yaml is valid
    for integration in integrations.values():
        validate_conditions(config, integration)
