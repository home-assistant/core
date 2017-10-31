"""
Support for Actions on Google Assistant Smart Home Control.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/google_assistant/
"""
import os
import asyncio
import logging

import aiohttp
import async_timeout

import voluptuous as vol

# Typing imports
# pylint: disable=using-constant-test,unused-import,ungrouped-imports
# if False:
from homeassistant.core import HomeAssistant  # NOQA
from typing import Dict, Any  # NOQA

from homeassistant import config as conf_util
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.loader import bind_hass

from .const import (
    DOMAIN, CONF_PROJECT_ID, CONF_CLIENT_ID, CONF_ACCESS_TOKEN,
    CONF_EXPOSE_BY_DEFAULT, CONF_EXPOSED_DOMAINS,
    CONF_AGENT_USER_ID, CONF_API_KEY,
    SERVICE_REQUEST_SYNC, REQUEST_SYNC_BASE_URL
)
from .auth import GoogleAssistantAuthView
from .http import GoogleAssistantView

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['http']

DEFAULT_AGENT_USER_ID = 'home-assistant'

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: {
            vol.Required(CONF_PROJECT_ID): cv.string,
            vol.Required(CONF_CLIENT_ID): cv.string,
            vol.Required(CONF_ACCESS_TOKEN): cv.string,
            vol.Optional(CONF_EXPOSE_BY_DEFAULT): cv.boolean,
            vol.Optional(CONF_EXPOSED_DOMAINS): cv.ensure_list,
            vol.Optional(CONF_AGENT_USER_ID,
                         default=DEFAULT_AGENT_USER_ID): cv.string,
            vol.Optional(CONF_API_KEY): cv.string
        }
    },
    extra=vol.ALLOW_EXTRA)


@bind_hass
def request_sync(hass):
    """Request sync."""
    hass.services.call(DOMAIN, SERVICE_REQUEST_SYNC)


@asyncio.coroutine
def async_setup(hass: HomeAssistant, yaml_config: Dict[str, Any]):
    """Activate Google Actions component."""
    config = yaml_config.get(DOMAIN, {})
    agent_user_id = config.get(CONF_AGENT_USER_ID)
    api_key = config.get(CONF_API_KEY)
    if api_key is not None:
        descriptions = yield from hass.async_add_job(
            conf_util.load_yaml_config_file, os.path.join(
                os.path.dirname(__file__), 'services.yaml')
        )
    hass.http.register_view(GoogleAssistantAuthView(hass, config))
    hass.http.register_view(GoogleAssistantView(hass, config))

    @asyncio.coroutine
    def request_sync_service_handler(call):
        """Handle request sync service calls."""
        websession = async_get_clientsession(hass)
        try:
            with async_timeout.timeout(5, loop=hass.loop):
                res = yield from websession.post(
                    REQUEST_SYNC_BASE_URL,
                    params={'key': api_key},
                    json={'agent_user_id': agent_user_id})
                _LOGGER.info("Submitted request_sync request to Google")
                res.raise_for_status()
        except aiohttp.ClientResponseError:
            body = yield from res.read()
            _LOGGER.error(
                'request_sync request failed: %d %s', res.status, body)
        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Could not contact Google for request_sync")

# Register service only if api key is provided
    if api_key is not None:
        hass.services.async_register(
            DOMAIN, SERVICE_REQUEST_SYNC, request_sync_service_handler,
            descriptions.get(SERVICE_REQUEST_SYNC))

    return True
