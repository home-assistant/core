"""Implement the serivces discovery feature from Hass.io for Add-ons."""
import asyncio
import logging
import os

import voluptuous as vol
from aiohttp import web
from aiohttp.web_exceptions import HTTPServiceUnavailable

from homeassistant.core import callback
from homeassistant.const import EVENT_HOMEASSISTANT_START
from homeassistant.components.http import HomeAssistantView
from homeassistant.helpers.discovery import async_load_platform, async_discover

from .handler import HassioAPIError

_LOGGER = logging.getLogger(__name__)

ATTR_DISCOVERY = 'discovery'
ATTR_ADDON = 'addon'
ATTR_NAME = 'name'
ATTR_SERVICE = 'service'
ATTR_CONFIG = 'config'
ATTR_COMPONENT = 'component'
ATTR_PLATFORM = 'platform'
ATTR_UUID = 'uuid'

CONFIG_FLOW_SERVICE = ('mqtt',)


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
            _LOGGER.error(
                "Can't read discover info: %s", err)
            return

        jobs = [hassio_discovery.async_process_new(discovery)
                for discovery in data[ATTR_DISCOVERY]]  
        if jobs:
            await asyncio.wait(jobs)

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

    async def post(self, request):
        """Handle new discovery requests."""
        uuid = request.match_info.get(uuid)

        # Fetch discovery data and prevent injections
        try:
            data = await self.hassio.get_discovery_message(uuid)
        except HassioAPIError as err:
            _LOGGER.error("Can't read discovey data: %s", err)
            raise HTTPServiceUnavailable() from None

        await self.async_process_new(self, data)
        return web.Response()

    async def delete(self, request):
        """Handle remove discovery requests."""
        data = request.json()

        await self.async_process_del(self, data)
        return web.Response()

    async def async_process_new(self, data):
        """Process add discovery entry."""
        service = data[ATTR_SERVICE]
        component = data[ATTR_COMPONENT]
        platform = data[ATTR_PLATFORM]
        config_data = data[ATTR_CONFIG]

        # Read addinional Add-on info
        try:
            addon_info = await self.hassio.get_addon_info(data[ATTR_ADDON])
        except HassioAPIError as err:
            _LOGGER.error("Can't read add-on info: %s", err)
            return

        # Use config flow
        if service in CONFIG_FLOW_SERVICE:
            # Replace Add-on ID with name 
            data[ATTR_ADDON] = addon_info[ATTR_NAME]

            await self.hass.config_entries.flow.async_init(
                service, context={'source': 'hass.io'}, data=config_data)
            return

        # Use discovery
        if platform is None:
            await async_discover(
                self.hass, service, config_data, component, self.config)
        else:
            await async_load_platform(
                self.hass, component, platform, config_data, self.config)

    async def async_process_del(self, data):
        """Process remove discovery entry."""
        service = data[ATTR_SERVICE]
        uuid = data[ATTR_UUID]

        # Check if realy deletet / prevent injections
        try:
            data = await self.hassio.get_discovery_message(uuid)
        except HassioAPIError as err:
            pass
        else:
            _LOGGER.warning("Retrieve a wrong unload discovery for %s", service)
            return

        # Use config flow
        if service not in CONFIG_FLOW_SERVICE:
            _LOGGER.info("Can't unload discovery for %s", service)
            return

        for entry in self.hass.config_entries.async_entries(service):
            if entry.source != 'hass.io':
                continue
            await self.hass.config_entries.async_remove(entry)
