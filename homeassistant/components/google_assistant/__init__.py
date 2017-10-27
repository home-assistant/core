"""
Support for Actions on Google Assistant Smart Home Control.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/google_assistant/
"""
import asyncio
import logging
import os
import voluptuous as vol

# Typing imports
# pylint: disable=using-constant-test,unused-import,ungrouped-imports
# if False:
from homeassistant.core import HomeAssistant  # NOQA
from typing import Dict, Any  # NOQA

from homeassistant import config as conf_util
from homeassistant.core import callback
from homeassistant.loader import bind_hass
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DOMAIN, CONF_PROJECT_ID, CONF_CLIENT_ID, CONF_ACCESS_TOKEN,
    CONF_EXPOSE_BY_DEFAULT, CONF_EXPOSED_DOMAINS,
    CONF_AGENT_USER_ID, CONF_API_KEY
)
from .auth import GoogleAssistantAuthView
from .http import GoogleAssistantView

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['http']

SERVICE_REQUEST_SYNC = "request_sync"
BASE_REQUEST_SYNC_URL = \
    "https://homegraph.googleapis.com/v1/devices:requestSync"

REQUEST_SYNC_SERVICE_SCHEMA = vol.Schema({})

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: {
            vol.Required(CONF_PROJECT_ID): cv.string,
            vol.Required(CONF_CLIENT_ID): cv.string,
            vol.Required(CONF_ACCESS_TOKEN): cv.string,
            vol.Optional(CONF_AGENT_USER_ID): cv.string,
            vol.Optional(CONF_API_KEY): cv.string,
            vol.Optional(CONF_EXPOSE_BY_DEFAULT): cv.boolean,
            vol.Optional(CONF_EXPOSED_DOMAINS): cv.ensure_list,
        }
    },
    extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup(hass: HomeAssistant, yaml_config: Dict[str, Any]):
    """Activate Google Actions component."""
    config = yaml_config.get(DOMAIN, {})

    descriptions = yield from hass.async_add_job(
        conf_util.load_yaml_config_file, os.path.join(
            os.path.dirname(__file__), 'services.yaml')
    )

    @asyncio.coroutine
    def request_sync_service_handler(service):
        """Request sync of devices."""
        session = async_get_clientsession(hass)
        yield from session.post(
            BASE_REQUEST_SYNC_URL,
            params={'key': config.get(CONF_API_KEY)},
            json={'agent_user_id': config.get(CONF_AGENT_USER_ID)})

        return

    if config.get(CONF_AGENT_USER_ID) is not None and \
       config.get(CONF_API_KEY) is not None:
        hass.services.async_register(
            DOMAIN, SERVICE_REQUEST_SYNC, request_sync_service_handler,
            descriptions[SERVICE_REQUEST_SYNC],
            schema=REQUEST_SYNC_SERVICE_SCHEMA)

    hass.http.register_view(GoogleAssistantAuthView(hass, config))
    hass.http.register_view(GoogleAssistantView(hass, config))

    return True


@bind_hass
def request_sync(hass):
    """Request sync of devices."""
    hass.add_job(async_request_sync, hass)


@callback
@bind_hass
def async_request_sync(hass):
    """Reload the automation from config."""
    hass.async_add_job(hass.services.async_call(DOMAIN, SERVICE_REQUEST_SYNC))
