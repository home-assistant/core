"""
Support for Actions on Google Assistant Smart Home Control.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/google_assistant/
"""
import asyncio
import logging

import voluptuous as vol

# Typing imports
# pylint: disable=using-constant-test,unused-import,ungrouped-imports
# if False:
from homeassistant.core import HomeAssistant  # NOQA
from typing import Dict, Any  # NOQA

from homeassistant.helpers import config_validation as cv

from .const import (
    DOMAIN, CONF_PROJECT_ID, CONF_CLIENT_ID, CONF_ACCESS_TOKEN,
    CONF_EXPOSE_BY_DEFAULT, CONF_EXPOSED_DOMAINS
)
from .auth import GoogleAssistantAuthView
from .http import GoogleAssistantView

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['http']

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: {
            vol.Required(CONF_PROJECT_ID): cv.string,
            vol.Required(CONF_CLIENT_ID): cv.string,
            vol.Required(CONF_ACCESS_TOKEN): cv.string,
            vol.Optional(CONF_EXPOSE_BY_DEFAULT): cv.boolean,
            vol.Optional(CONF_EXPOSED_DOMAINS): cv.ensure_list,
        }
    },
    extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup(hass: HomeAssistant, yaml_config: Dict[str, Any]):
    """Activate Google Actions component."""
    config = yaml_config.get(DOMAIN, {})

    hass.http.register_view(GoogleAssistantAuthView(hass, config))
    hass.http.register_view(GoogleAssistantView(hass, config))

    return True
