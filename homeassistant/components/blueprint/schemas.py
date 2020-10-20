"""Schemas for the blueprint integration."""
import voluptuous as vol

from homeassistant.const import CONF_DOMAIN, CONF_NAME, CONF_PATH
from homeassistant.helpers import config_validation as cv

from .const import CONF_BLUEPRINT, CONF_INPUT

BLUEPRINT_SCHEMA = vol.Schema(
    {
        # No definition yet for the inputs.
        vol.Required(CONF_BLUEPRINT): vol.Schema(
            {
                vol.Required(CONF_NAME): str,
                vol.Required(CONF_DOMAIN): str,
                vol.Optional(CONF_INPUT, default=dict): {str: None},
            }
        ),
    },
    extra=vol.ALLOW_EXTRA,
)

BLUEPRINT_INSTANCE_FIELDS = vol.Schema(
    {
        vol.Required(CONF_BLUEPRINT): vol.Schema(
            {
                vol.Required(CONF_PATH): cv.path,
                vol.Required(CONF_INPUT): {str: cv.match_all},
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)
