"""Implement the serivces discovery feature from Hass.io for Add-ons."""
import asyncio
import logging
import os

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.const import EVENT_HOMEASSISTANT_START

from .handler import HassioAPIError

_LOGGER = logging.getLogger(__name__)

EVENT_DISCOVERY_ADD = 'hassio_discovery_add'
EVENT_DISCOVERY_DEL = 'hassio_discovery_del'

ATTR_UUID = 'uuid'
ATTR_DISCOVERY = 'discovery'


@callback
def async_setup_discovery(hass, hassio):
    """Discovery setup."""
    async def async_discovery_event_handler(event):
        """Handle events from Hass.io discovery."""
        uuid = event.data[ATTR_UUID]

        try:
            data = await hassio.get_services_discovery(uuid)
        except HassioAPIError as err:
            _LOGGER.error(
                "Can't read discover %s info: %s", uuid, err)
            return

        hass.async_add_job(async_process_discovery, hass, data)

    hass.bus.async_listen(
        EVENT_DISCOVERY_ADD, async_discovery_event_handler)

    async def async_discovery_start_handler(event):
        """Process all exists discovery on startup."""
        try:
            data = await hassio.get_services_discovery(uuid)
        except HassioAPIError as err:
            _LOGGER.error(
                "Can't read discover %s info: %s", uuid, err)
            return

        for discovery in data[ATTR_DISCOVERY]:
            hass.async_add_job(async_process_discovery, hass, discovery)

    hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_START, async_discovery_start_handler)


@callback
def async_process_discovery(hass, data):
    """Process a discovery request."""
