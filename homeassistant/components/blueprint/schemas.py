"""Schemas for the blueprint integration."""
from typing import Any

import voluptuous as vol

from homeassistant.const import (
    CONF_DEFAULT,
    CONF_DESCRIPTION,
    CONF_DOMAIN,
    CONF_NAME,
    CONF_PATH,
    CONF_SELECTOR,
)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv, selector

from .const import (
    CONF_AUTHOR,
    CONF_BLUEPRINT,
    CONF_HOMEASSISTANT,
    CONF_INPUT,
    CONF_MIN_VERSION,
    CONF_SOURCE_URL,
    CONF_USE_BLUEPRINT,
)


def version_validator(value: Any) -> str:
    """Validate a Home Assistant version."""
    if not isinstance(value, str):
        raise vol.Invalid("Version needs to be a string")

    parts = value.split(".")

    if len(parts) != 3:
        raise vol.Invalid("Version needs to be formatted as {major}.{minor}.{patch}")

    try:
        [int(p) for p in parts]
    except ValueError:
        raise vol.Invalid(
            "Major, minor and patch version needs to be an integer"
        ) from None

    return value


@callback
def is_blueprint_config(config: Any) -> bool:
    """Return if it is a blueprint config."""
    return isinstance(config, dict) and CONF_BLUEPRINT in config


@callback
def is_blueprint_instance_config(config: Any) -> bool:
    """Return if it is a blueprint instance config."""
    return isinstance(config, dict) and CONF_USE_BLUEPRINT in config


BLUEPRINT_INPUT_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME): str,
        vol.Optional(CONF_DESCRIPTION): str,
        vol.Optional(CONF_DEFAULT): cv.match_all,
        vol.Optional(CONF_SELECTOR): selector.validate_selector,
    }
)

BLUEPRINT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_BLUEPRINT): vol.Schema(
            {
                vol.Required(CONF_NAME): str,
                vol.Optional(CONF_DESCRIPTION): str,
                vol.Required(CONF_DOMAIN): str,
                vol.Optional(CONF_SOURCE_URL): cv.url,
                vol.Optional(CONF_AUTHOR): str,
                vol.Optional(CONF_HOMEASSISTANT): {
                    vol.Optional(CONF_MIN_VERSION): version_validator
                },
                vol.Optional(CONF_INPUT, default=dict): {
                    str: vol.Any(
                        None,
                        BLUEPRINT_INPUT_SCHEMA,
                    )
                },
            }
        ),
    },
    extra=vol.ALLOW_EXTRA,
)


def validate_yaml_suffix(value: str) -> str:
    """Validate value has a YAML suffix."""
    if not value.endswith(".yaml"):
        raise vol.Invalid("Path needs to end in .yaml")
    return value


BLUEPRINT_INSTANCE_FIELDS = vol.Schema(
    {
        vol.Required(CONF_USE_BLUEPRINT): vol.Schema(
            {
                vol.Required(CONF_PATH): vol.All(cv.path, validate_yaml_suffix),
                vol.Required(CONF_INPUT, default=dict): {str: cv.match_all},
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)
