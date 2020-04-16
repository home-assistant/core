"""Validate integration translation files."""
import json
from typing import Dict

import voluptuous as vol
from voluptuous.humanize import humanize_error

from .model import Integration

UNDEFINED = 0
REQUIRED = 1
REMOVED = 2

REMOVED_TITLE_MSG = (
    "config.title key has been moved out of config and into the root of strings.json. "
    "Starting Home Assistant 0.109 you only need to define this key in the root "
    "if the title needs to be different than the name of your integration in the "
    "manifest."
)


def removed_title_validator(value):
    """Mark removed title."""
    raise vol.Invalid(REMOVED_TITLE_MSG)


def data_entry_schema(*, flow_title: int, require_step_title: bool):
    """Generate a data entry schema."""
    step_title_class = vol.Required if require_step_title else vol.Optional
    data_entry_schema = {
        vol.Optional("flow_title"): str,
        vol.Required("step"): {
            str: {
                step_title_class("title"): str,
                vol.Optional("description"): str,
                vol.Optional("data"): {str: str},
            }
        },
        vol.Optional("error"): {str: str},
        vol.Optional("abort"): {str: str},
        vol.Optional("create_entry"): {str: str},
    }
    if flow_title == REQUIRED:
        data_entry_schema[vol.Required("title")] = str
    elif flow_title == REMOVED:
        data_entry_schema[
            vol.Optional("title", msg=REMOVED_TITLE_MSG)
        ] = removed_title_validator

    return data_entry_schema


STRINGS_SCHEMA = vol.Schema(
    {
        vol.Optional("title"): str,
        vol.Optional("config"): data_entry_schema(
            flow_title=REMOVED, require_step_title=True
        ),
        vol.Optional("options"): data_entry_schema(
            flow_title=UNDEFINED, require_step_title=False
        ),
        vol.Optional("device_automation"): {
            vol.Optional("action_type"): {str: str},
            vol.Optional("condition_type"): {str: str},
            vol.Optional("trigger_type"): {str: str},
            vol.Optional("trigger_subtype"): {str: str},
        },
        vol.Optional("state"): {str: str},
    }
)

AUTH_SCHEMA = vol.Schema(
    {
        vol.Optional("mfa_setup"): {
            str: data_entry_schema(flow_title=REQUIRED, require_step_title=True)
        }
    }
)

ONBOARDING_SCHEMA = vol.Schema({vol.Required("area"): {str: str}})


def validate_translation_file(integration: Integration):
    """Validate translation files for integration."""
    strings_file = integration.path / "strings.json"

    if not strings_file.is_file():
        return

    strings = json.loads(strings_file.read_text())

    if integration.domain == "auth":
        schema = AUTH_SCHEMA
    elif integration.domain == "onboarding":
        schema = ONBOARDING_SCHEMA
    else:
        schema = STRINGS_SCHEMA

    try:
        schema(strings)
    except vol.Invalid as err:
        integration.add_error(
            "translations", f"Invalid strings.json: {humanize_error(strings, err)}"
        )


def validate(integrations: Dict[str, Integration], config):
    """Handle JSON files inside integrations."""
    for integration in integrations.values():
        validate_translation_file(integration)
