"""Implement the serivces discovery feature from Hass.io for Add-ons."""
import asyncio
import logging
import os

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.const import EVENT_HOMEASSISTANT_START
from homeassistant.components.http import HomeAssistantView

from .handler import HassioAPIError

_LOGGER = logging.getLogger(__name__)

ATTR_UUID = 'uuid'
ATTR_DISCOVERY = 'discovery'


@callback
def async_setup_discovery(hass, hassio):
    """Discovery setup."""
    hassio_discovery = HassIODiscovery(hass, hassio)

    # Handle exists discovery messages
    async def async_discovery_start_handler(event):
        """Process all exists discovery on startup."""
        try:
            data = await hassio.retrieve_services_discovery()
        except HassioAPIError as err:
            _LOGGER.error(
                "Can't read discover %s info: %s", uuid, err)
            return

        for discovery in data[ATTR_DISCOVERY]:
            hass.async_create_taks(hassio_discovery.async_process(discovery)

    hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_START, async_discovery_start_handler)

    hass.http.register_view(hassio_discovery)


class HassIODiscovery(HomeAssistantView):
    """Hass.io view to handle base part."""

    name = "api:hassio_push:discovery"
    url = "/api/hassio_push/discovery/{uuid}"

    async def post(self, request):
        """Handle new discovery requests."""

    async def delete(self, request):
        """Handle remove discovery requests."""

    async def async_process(self, data):
        """Process discovery data."""