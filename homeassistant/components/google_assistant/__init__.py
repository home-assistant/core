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
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.loader import bind_hass

from .const import (
    DOMAIN, CONF_PROJECT_ID, CONF_CLIENT_ID, CONF_ACCESS_TOKEN,
    CONF_EXPOSE_BY_DEFAULT, CONF_EXPOSED_DOMAINS, CONF_AGENT_USER_ID, CONF_HOMEGRAPH_API_KEY, SERVICE_REQUEST_SYNC, REQUEST_SYNC_URL
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
            vol.Required(CONF_AGENT_USER_ID): cv.string,
            vol.Required(CONF_HOMEGRAPH_API_KEY): cv.string
        }
    },
    extra=vol.ALLOW_EXTRA)

def request_sync(hass):
    """Request sync."""
    hass.services.call(DOMAIN, SERVICE_REQUEST_SYNC)

@asyncio.coroutine
def async_setup(hass: HomeAssistant, yaml_config: Dict[str, Any]):
    """Activate Google Actions component."""
    config = yaml_config.get(DOMAIN, {})

    hass.http.register_view(GoogleAssistantAuthView(hass, config))
    hass.http.register_view(GoogleAssistantView(hass, config))

    @asyncio.coroutine
    def request_sync_service_handler(call):
        """Handle request sync service calls."""
        #Code to execute request sync goes here
        websession = async_get_clientsession(hass) 
        try:
            agent_user_id = config.get(CONF_AGENT_USER_ID);
	    with async_timeout.timeout(5, loop=hass.loop):
	       req = yield from session.post(REQUEST_SYNC_URL+CONF_HOMEGRAPH_API_KEY, json={'agent_user_id': agent_user_id})
	       _LOGGER.info("Submitted request_sync request to Google")
	    except (asyncio.TimeoutError, aiohttp.ClientError):
	        _LOGGER.error("Could not contact Google for request_sync")
        return None
    
    hass.services.async_register(
 	    DOMAIN, SERVICE_REQUEST_SYNC, request_sync_service_handler,
	    descriptions.get(SERVICE_REQUEST_SYNC))

    return True
