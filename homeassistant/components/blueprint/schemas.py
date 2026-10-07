"""Schemas for the blueprint integration."""

from typing import Any

import probatio

from homeassistant.const import (
    CONF_DEFAULT,
    CONF_DESCRIPTION,
    CONF_DOMAIN,
    CONF_ICON,
    CONF_NAME,
    CONF_PATH,
    CONF_SELECTOR,
)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv, selector

from .const import (
    CONF_AUTHOR,
    CONF_BLUEPRINT,
    CONF_COLLAPSED,
    CONF_HOMEASSISTANT,
    CONF_INPUT,
    CONF_MIN_VERSION,
    CONF_SOURCE_URL,
    CONF_USE_BLUEPRINT,
)


def version_validator(value: Any) -> str:
    """Validate a Home Assistant version."""
    if not isinstance(value, str):
        raise probatio.Invalid("Version needs to be a string")

    parts = value.split(".")

    if len(parts) != 3:
        raise probatio.Invalid(
            "Version needs to be formatted as {major}.{minor}.{patch}"
        )

    try:
        [int(p) for p in parts]
    except ValueError:
        raise probatio.Invalid(
            "Major, minor and patch version needs to be an integer"
        ) from None

    return value


def unique_input_validator(inputs: Any) -> Any:
    """Validate the inputs don't have duplicate keys under different sections."""
    all_inputs = set()
    for key, value in inputs.items():
        if value and CONF_INPUT in value:
            for key in value[CONF_INPUT]:
                if key in all_inputs:
                    raise probatio.Invalid(
                        f"Duplicate use of input key {key} in blueprint."
                    )
                all_inputs.add(key)
        else:
            if key in all_inputs:
                raise probatio.Invalid(
                    f"Duplicate use of input key {key} in blueprint."
                )
            all_inputs.add(key)

    return inputs


@callback
def is_blueprint_config(config: Any) -> bool:
    """Return if it is a blueprint config."""
    return isinstance(config, dict) and CONF_BLUEPRINT in config


@callback
def is_blueprint_instance_config(config: Any) -> bool:
    """Return if it is a blueprint instance config."""
    return isinstance(config, dict) and CONF_USE_BLUEPRINT in config


BLUEPRINT_INPUT_SCHEMA = probatio.Schema(
    {
        probatio.Optional(CONF_NAME): str,
        probatio.Optional(CONF_DESCRIPTION): str,
        probatio.Optional(CONF_DEFAULT): cv.match_all,
        probatio.Optional(CONF_SELECTOR): selector.validate_selector,
    }
)

BLUEPRINT_INPUT_SECTION_SCHEMA = probatio.Schema(
    {
        probatio.Optional(CONF_NAME): str,
        probatio.Optional(CONF_ICON): str,
        probatio.Optional(CONF_DESCRIPTION): str,
        probatio.Optional(CONF_COLLAPSED): bool,
        probatio.Required(CONF_INPUT, default=dict): {
            str: probatio.Any(
                None,
                BLUEPRINT_INPUT_SCHEMA,
            )
        },
    }
)

BLUEPRINT_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_BLUEPRINT): probatio.Schema(
            {
                probatio.Required(CONF_NAME): str,
                probatio.Optional(CONF_DESCRIPTION): str,
                probatio.Required(CONF_DOMAIN): str,
                probatio.Optional(CONF_SOURCE_URL): cv.url,
                probatio.Optional(CONF_AUTHOR): str,
                probatio.Optional(CONF_HOMEASSISTANT): {
                    probatio.Optional(CONF_MIN_VERSION): version_validator
                },
                probatio.Optional(CONF_INPUT, default=dict): probatio.All(
                    {
                        str: probatio.Any(
                            None,
                            BLUEPRINT_INPUT_SCHEMA,
                            BLUEPRINT_INPUT_SECTION_SCHEMA,
                        )
                    },
                    unique_input_validator,
                ),
            }
        ),
    },
    extra=probatio.ALLOW_EXTRA,
)


def validate_yaml_suffix(value: str) -> str:
    """Validate value has a YAML suffix."""
    if not value.endswith(".yaml"):
        raise probatio.Invalid("Path needs to end in .yaml")
    return value


BLUEPRINT_INSTANCE_FIELDS = probatio.Schema(
    {
        probatio.Required(CONF_USE_BLUEPRINT): probatio.Schema(
            {
                probatio.Required(CONF_PATH): probatio.All(
                    cv.path, validate_yaml_suffix
                ),
                probatio.Required(CONF_INPUT, default=dict): {str: cv.match_all},
            }
        )
    },
    extra=probatio.ALLOW_EXTRA,
)
