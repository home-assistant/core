"""Validate integration translation files."""
from functools import partial
import json
import logging
from typing import Dict

import voluptuous as vol
from voluptuous.humanize import humanize_error

import homeassistant.helpers.config_validation as cv
from homeassistant.util import slugify

from .model import Config, Integration

_LOGGER = logging.getLogger(__name__)

UNDEFINED = 0
REQUIRED = 1
REMOVED = 2

REMOVED_TITLE_MSG = (
    "config.title key has been moved out of config and into the root of strings.json. "
    "Starting Home Assistant 0.109 you only need to define this key in the root "
    "if the title needs to be different than the name of your integration in the "
    "manifest."
)


def removed_title_validator(config, integration, value):
    """Mark removed title."""
    if not config.specific_integrations:
        raise vol.Invalid(REMOVED_TITLE_MSG)

    # Don't mark it as an error yet for custom components to allow backwards compat.
    integration.add_warning("translations", REMOVED_TITLE_MSG)
    return value


def gen_data_entry_schema(
    *,
    config: Config,
    integration: Integration,
    flow_title: int,
    require_step_title: bool,
):
    """Generate a data entry schema."""
    step_title_class = vol.Required if require_step_title else vol.Optional
    schema = {
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
        schema[vol.Required("title")] = str
    elif flow_title == REMOVED:
        schema[vol.Optional("title", msg=REMOVED_TITLE_MSG)] = partial(
            removed_title_validator, config, integration
        )

    return schema


def gen_strings_schema(config: Config, integration: Integration):
    """Generate a strings schema."""
    return vol.Schema(
        {
            vol.Optional("title"): str,
            vol.Optional("config"): gen_data_entry_schema(
                config=config,
                integration=integration,
                flow_title=REMOVED,
                require_step_title=True,
            ),
            vol.Optional("options"): gen_data_entry_schema(
                config=config,
                integration=integration,
                flow_title=UNDEFINED,
                require_step_title=False,
            ),
            vol.Optional("device_automation"): {
                vol.Optional("action_type"): {str: str},
                vol.Optional("condition_type"): {str: str},
                vol.Optional("trigger_type"): {str: str},
                vol.Optional("trigger_subtype"): {str: str},
            },
            vol.Optional("state"): cv.schema_with_slug_keys(
                cv.schema_with_slug_keys(str)
            ),
        }
    )


def gen_auth_schema(config: Config, integration: Integration):
    """Generate auth schema."""
    return vol.Schema(
        {
            vol.Optional("mfa_setup"): {
                str: gen_data_entry_schema(
                    config=config,
                    integration=integration,
                    flow_title=REQUIRED,
                    require_step_title=True,
                )
            }
        }
    )


def gen_platform_strings_schema(config: Config, integration: Integration):
    """Generate platform strings schema like strings.sensor.json."""

    def device_class_validator(value):
        """Key validator."""
        if not value.startswith(f"{integration.domain}__"):
            raise vol.Invalid(
                f"Device class need to start with '{integration.domain}__'. Key {value} is invalid"
            )

        slug_friendly = value.replace("__", "_", 1)
        slugged = slugify(slug_friendly)

        if slug_friendly != slugged:
            raise vol.Invalid(f"invalid device class {value}")

        return value

    return vol.Schema(
        {
            vol.Optional("state"): cv.schema_with_slug_keys(
                cv.schema_with_slug_keys(str), slug_validator=device_class_validator
            )
        }
    )


ONBOARDING_SCHEMA = vol.Schema({vol.Required("area"): {str: str}})


def validate_translation_file(config: Config, integration: Integration):
    """Validate translation files for integration."""
    strings_file = integration.path / "strings.json"

    if strings_file.is_file():
        strings = json.loads(strings_file.read_text())

        if integration.domain == "auth":
            schema = gen_auth_schema(config, integration)
        elif integration.domain == "onboarding":
            schema = ONBOARDING_SCHEMA
        else:
            schema = gen_strings_schema(config, integration)

        try:
            schema(strings)
        except vol.Invalid as err:
            integration.add_error(
                "translations", f"Invalid strings.json: {humanize_error(strings, err)}"
            )

    for path in integration.path.glob("strings.*.json"):
        strings = json.loads(path.read_text())
        schema = gen_platform_strings_schema(config, integration)

        try:
            schema(strings)
        except vol.Invalid as err:
            msg = f"Invalid {path.name}: {humanize_error(strings, err)}"
            if config.specific_integrations:
                integration.add_warning("translations", msg)
            else:
                integration.add_error("translations", msg)


def validate(integrations: Dict[str, Integration], config: Config):
    """Handle JSON files inside integrations."""
    for integration in integrations.values():
        validate_translation_file(config, integration)
