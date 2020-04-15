"""Check translation files."""
import json

import voluptuous as vol
from voluptuous.humanize import humanize_error

from .const import INTEGRATIONS_DIR


def data_entry_schema(*, require_title: bool, require_step_title: bool):
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
    if require_title:
        data_entry_schema[vol.Required("title")] = str

    return data_entry_schema


STRINGS_SCHEMA = vol.Schema(
    {
        vol.Optional("title"): str,
        vol.Optional("config"): data_entry_schema(
            require_title=False, require_step_title=True
        ),
        vol.Optional("options"): data_entry_schema(
            require_title=False, require_step_title=False
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
            str: data_entry_schema(require_title=True, require_step_title=True)
        }
    }
)

ONBOARDING_SCHEMA = vol.Schema({vol.Required("area"): {str: str}})


def run():
    """Check all integrations."""
    errors = []

    for integration in INTEGRATIONS_DIR.iterdir():
        strings_file = integration / "strings.json"
        if not strings_file.is_file():
            continue

        strings = json.loads(strings_file.read_text())

        if integration.name == "auth":
            schema = AUTH_SCHEMA
        elif integration.name == "onboarding":
            schema = ONBOARDING_SCHEMA
        else:
            schema = STRINGS_SCHEMA

        try:
            schema(strings)
        except vol.Invalid as err:
            errors.append(
                f"{integration.name} - invalid strings.json: {humanize_error(strings, err)}"
            )

    if not errors:
        return 0

    print(f"Found {len(errors)} errors")
    print()

    for error in errors:
        print(error)
        print()

    return 1
