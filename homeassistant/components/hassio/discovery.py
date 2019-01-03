"""Implement the serivces discovery feature from Hass.io for Add-ons."""
import asyncio
import logging

from aiohttp import web
from aiohttp.web_exceptions import HTTPServiceUnavailable

from homeassistant.core import callback, CoreState
from homeassistant.const import EVENT_HOMEASSISTANT_START
from homeassistant.components.http import HomeAssistantView

from .handler import HassioAPIError
from .const import (
    ATTR_DISCOVERY, ATTR_ADDON, ATTR_NAME, ATTR_SERVICE, ATTR_CONFIG,
    ATTR_UUID)

_LOGGER = logging.getLogger(__name__)


@callback
def async_setup_discovery(hass, hassio, config):
    """Discovery setup."""
    hassio_discovery = HassIODiscovery(hass, hassio, config)

    # Handle exists discovery messages
    async def async_discovery_start_handler(event):
        """Process all exists discovery on startup."""
        try:
            data = await hassio.retrieve_discovery_messages()
        except HassioAPIError as err:
            _LOGGER.error("Can't read discover info: %s", err)
            return

        jobs = [hassio_discovery.async_process_new(discovery)
                for discovery in data[ATTR_DISCOVERY]]
        if jobs:
            await asyncio.wait(jobs)

    if hass.state == CoreState.running:
        hass.async_create_task(async_discovery_start_handler(None))
    else:
        hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, async_discovery_start_handler)

    hass.http.register_view(hassio_discovery)


class HassIODiscovery(HomeAssistantView):
    """Hass.io view to handle base part."""

    name = "api:hassio_push:discovery"
    url = "/api/hassio_push/discovery/{uuid}"

    def __init__(self, hass, hassio, config):
        """Initialize WebView."""
        self.hass = hass
        self.hassio = hassio
        self.config = config

    async def post(self, request, uuid):
        """Handle new discovery requests."""
        # Fetch discovery data and prevent injections
        try:
            data = await self.hassio.get_discovery_message(uuid)
        except HassioAPIError as err:
            _LOGGER.error("Can't read discovey data: %s", err)
            raise HTTPServiceUnavailable() from None

        await self.async_process_new(data)
        return web.Response()

    async def delete(self, request, uuid):
        """Handle remove discovery requests."""
        data = await request.json()

        await self.async_process_del(data)
        return web.Response()

    async def async_process_new(self, data):
        """Process add discovery entry."""
        service = data[ATTR_SERVICE]
        config_data = data[ATTR_CONFIG]

        # Read addinional Add-on info
        try:
            addon_info = await self.hassio.get_addon_info(data[ATTR_ADDON])
        except HassioAPIError as err:
            _LOGGER.error("Can't read add-on info: %s", err)
            return
        config_data[ATTR_ADDON] = addon_info[ATTR_NAME]

        # Use config flow
        await self.hass.config_entries.flow.async_init(
            service, context={'source': 'hassio'}, data=config_data)

    async def async_process_del(self, data):
        """Process remove discovery entry."""
        service = data[ATTR_SERVICE]
        uuid = data[ATTR_UUID]

        # Check if realy deletet / prevent injections
        try:
            data = await self.hassio.get_discovery_message(uuid)
        except HassioAPIError:
            pass
        else:
            _LOGGER.warning("Retrieve wrong unload for %s", service)
            return

        # Use config flow
        for entry in self.hass.config_entries.async_entries(service):
            if entry.source != 'hassio':
                continue
            await self.hass.config_entries.async_remove(entry)
