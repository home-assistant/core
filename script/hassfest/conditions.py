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


def validate_field_schema(condition_schema: dict[str, Any]) -> dict[str, Any]:
    """Validate a field schema including context references."""

    for field_name, field_schema in condition_schema.get("fields", {}).items():
        # Validate context if present
        if "context" in field_schema:
            if CONF_SELECTOR not in field_schema:
                raise vol.Invalid(
                    f"Context defined without a selector in '{field_name}'"
                )

            context = field_schema["context"]
            if not isinstance(context, dict):
                raise vol.Invalid(f"Context must be a dictionary in '{field_name}'")

            # Determine which selector type is being used
            selector_config = field_schema[CONF_SELECTOR]
            selector_class = selector.selector(selector_config)

            for context_key, field_ref in context.items():
                # Check if context key is allowed for this selector type
                allowed_keys = selector_class.allowed_context_keys
                if context_key not in allowed_keys:
                    raise vol.Invalid(
                        f"Invalid context key '{context_key}' for selector type '{selector_class.selector_type}'. "
                        f"Allowed keys: {', '.join(sorted(allowed_keys)) if allowed_keys else 'none'}"
                    )

                # Check if the referenced field exists in condition schema or target
                if not isinstance(field_ref, str):
                    raise vol.Invalid(
                        f"Context value for '{context_key}' must be a string field reference"
                    )

                # Check if field exists in condition schema fields or target
                condition_fields = condition_schema["fields"]
                field_exists = field_ref in condition_fields
                if field_exists and "selector" in condition_fields[field_ref]:
                    # Check if the selector type is allowed for this context key
                    field_selector_config = condition_fields[field_ref][CONF_SELECTOR]
                    field_selector_class = selector.selector(field_selector_config)
                    if field_selector_class.selector_type not in allowed_keys.get(
                        context_key, set()
                    ):
                        raise vol.Invalid(
                            f"The context '{context_key}' for '{field_name}' references '{field_ref}', but '{context_key}' "
                            f"does not allow selectors of type '{field_selector_class.selector_type}'. Allowed selector types: {', '.join(allowed_keys.get(context_key, set()))}"
                        )
                if not field_exists and "target" in condition_schema:
                    # Target is a special field that always exists when defined
                    field_exists = field_ref == "target"
                    if field_exists and "target" not in allowed_keys.get(
                        context_key, set()
                    ):
                        raise vol.Invalid(
                            f"The context '{context_key}' for '{field_name}' references 'target', but '{context_key}' "
                            f"does not allow 'target'. Allowed selector types: {', '.join(allowed_keys.get(context_key, set()))}"
                        )

                if not field_exists:
                    raise vol.Invalid(
                        f"Context reference '{field_ref}' for key '{context_key}' does not exist "
                        f"in condition schema fields or target"
                    )

    return condition_schema


FIELD_SCHEMA = vol.Schema(
    {
        vol.Optional("example"): exists,
        vol.Optional("default"): exists,
        vol.Optional("required"): bool,
        vol.Optional(CONF_SELECTOR): selector.validate_selector,
        vol.Optional("context"): {
            str: str  # key is context key, value is field name in the schema which value should be used
        },  # Will be validated in validate_field_schema
    }
)

CONDITION_SCHEMA = vol.Any(
    vol.All(
        vol.Schema(
            {
                vol.Optional("target"): selector.TargetSelector.CONFIG_SCHEMA,
                vol.Optional("fields"): vol.Schema({str: FIELD_SCHEMA}),
            }
        ),
        validate_field_schema,
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
