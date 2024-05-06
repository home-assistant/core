"""Implement the services discovery feature from Hass.io for Add-ons."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
from typing import Any

from aiohttp import web
from aiohttp.web_exceptions import HTTPServiceUnavailable

from homeassistant import config_entries
from homeassistant.components.http import HomeAssistantView
from homeassistant.const import ATTR_NAME, ATTR_SERVICE, EVENT_HOMEASSISTANT_START
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.data_entry_flow import BaseServiceInfo
from homeassistant.helpers import discovery_flow

from .const import ATTR_ADDON, ATTR_CONFIG, ATTR_DISCOVERY, ATTR_UUID
from .handler import HassIO, HassioAPIError

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class HassioServiceInfo(BaseServiceInfo):
    """Prepared info from hassio entries."""

    config: dict[str, Any]
    name: str
    slug: str
    uuid: str


@callback
def async_setup_discovery_view(hass: HomeAssistant, hassio: HassIO) -> None:
    """Discovery setup."""
    hassio_discovery = HassIODiscovery(hass, hassio)
    hass.http.register_view(hassio_discovery)

    # Handle exists discovery messages
    async def _async_discovery_start_handler(event: Event) -> None:
        """Process all exists discovery on startup."""
        try:
            data = await hassio.retrieve_discovery_messages()
        except HassioAPIError as err:
            _LOGGER.error("Can't read discover info: %s", err)
            return

        jobs = [
            asyncio.create_task(hassio_discovery.async_process_new(discovery))
            for discovery in data[ATTR_DISCOVERY]
        ]
        if jobs:
            await asyncio.wait(jobs)

    hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_START, _async_discovery_start_handler
    )


class HassIODiscovery(HomeAssistantView):
    """Hass.io view to handle base part."""

    name = "api:hassio_push:discovery"
    url = "/api/hassio_push/discovery/{uuid}"

    def __init__(self, hass: HomeAssistant, hassio: HassIO) -> None:
        """Initialize WebView."""
        self.hass = hass
        self.hassio = hassio

    async def post(self, request: web.Request, uuid: str) -> web.Response:
        """Handle new discovery requests."""
        # Fetch discovery data and prevent injections
        try:
            data = await self.hassio.get_discovery_message(uuid)
        except HassioAPIError as err:
            _LOGGER.error("Can't read discovery data: %s", err)
            raise HTTPServiceUnavailable() from None

        await self.async_process_new(data)
        return web.Response()

    async def delete(self, request: web.Request, uuid: str) -> web.Response:
        """Handle remove discovery requests."""
        data: dict[str, Any] = await request.json()

        await self.async_process_del(data)
        return web.Response()

    async def async_process_new(self, data: dict[str, Any]) -> None:
        """Process add discovery entry."""
        service: str = data[ATTR_SERVICE]
        config_data: dict[str, Any] = data[ATTR_CONFIG]
        slug: str = data[ATTR_ADDON]
        uuid: str = data[ATTR_UUID]

        # Read additional Add-on info
        try:
            addon_info = await self.hassio.get_addon_info(slug)
        except HassioAPIError as err:
            _LOGGER.error("Can't read add-on info: %s", err)
            return

        name: str = addon_info[ATTR_NAME]
        config_data[ATTR_ADDON] = name

        # Use config flow
        discovery_flow.async_create_flow(
            self.hass,
            service,
            context={"source": config_entries.SOURCE_HASSIO},
            data=HassioServiceInfo(config=config_data, name=name, slug=slug, uuid=uuid),
        )

    async def async_process_del(self, data: dict[str, Any]) -> None:
        """Process remove discovery entry."""
        service = data[ATTR_SERVICE]
        uuid = data[ATTR_UUID]

        # Check if really deletet / prevent injections
        try:
            data = await self.hassio.get_discovery_message(uuid)
        except HassioAPIError:
            pass
        else:
            _LOGGER.warning("Retrieve wrong unload for %s", service)
            return

        # Use config flow
        for entry in self.hass.config_entries.async_entries(service):
            if entry.source != config_entries.SOURCE_HASSIO or entry.unique_id != uuid:
                continue
            await self.hass.config_entries.async_remove(entry.entry_id)
