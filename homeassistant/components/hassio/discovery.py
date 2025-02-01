"""Implement the services discovery feature from Hass.io for Add-ons."""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import UUID

from aiohasupervisor import SupervisorError
from aiohasupervisor.models import Discovery
from aiohttp import web
from aiohttp.web_exceptions import HTTPServiceUnavailable

from homeassistant import config_entries
from homeassistant.components.http import HomeAssistantView
from homeassistant.const import ATTR_SERVICE, EVENT_HOMEASSISTANT_START
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import discovery_flow
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.service_info.hassio import HassioServiceInfo

from .const import ATTR_ADDON, ATTR_UUID, DOMAIN
from .handler import HassIO, get_supervisor_client

_LOGGER = logging.getLogger(__name__)


@callback
def async_setup_discovery_view(hass: HomeAssistant, hassio: HassIO) -> None:
    """Discovery setup."""
    hassio_discovery = HassIODiscovery(hass, hassio)
    supervisor_client = get_supervisor_client(hass)
    hass.http.register_view(hassio_discovery)

    # Handle exists discovery messages
    async def _async_discovery_start_handler(event: Event) -> None:
        """Process all exists discovery on startup."""
        try:
            data = await supervisor_client.discovery.list()
        except SupervisorError as err:
            _LOGGER.error("Can't read discover info: %s", err)
            return

        jobs = [
            asyncio.create_task(hassio_discovery.async_process_new(discovery))
            for discovery in data
        ]
        if jobs:
            await asyncio.wait(jobs)

    hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_START, _async_discovery_start_handler
    )

    async def _handle_config_entry_removed(
        entry: config_entries.ConfigEntry,
    ) -> None:
        """Handle config entry changes."""
        for disc_key in entry.discovery_keys[DOMAIN]:
            if disc_key.version != 1 or not isinstance(key := disc_key.key, str):
                continue
            uuid = key
            _LOGGER.debug("Rediscover addon %s", uuid)
            await hassio_discovery.async_rediscover(uuid)

    async_dispatcher_connect(
        hass,
        config_entries.signal_discovered_config_entry_removed(DOMAIN),
        _handle_config_entry_removed,
    )


class HassIODiscovery(HomeAssistantView):
    """Hass.io view to handle base part."""

    name = "api:hassio_push:discovery"
    url = "/api/hassio_push/discovery/{uuid}"

    def __init__(self, hass: HomeAssistant, hassio: HassIO) -> None:
        """Initialize WebView."""
        self.hass = hass
        self.hassio = hassio
        self._supervisor_client = get_supervisor_client(hass)

    async def post(self, request: web.Request, uuid: str) -> web.Response:
        """Handle new discovery requests."""
        # Fetch discovery data and prevent injections
        try:
            data = await self._supervisor_client.discovery.get(UUID(uuid))
        except SupervisorError as err:
            _LOGGER.error("Can't read discovery data: %s", err)
            raise HTTPServiceUnavailable from None

        await self.async_process_new(data)
        return web.Response()

    async def delete(self, request: web.Request, uuid: str) -> web.Response:
        """Handle remove discovery requests."""
        data: dict[str, Any] = await request.json()

        await self.async_process_del(data)
        return web.Response()

    async def async_rediscover(self, uuid: str) -> None:
        """Rediscover add-on when config entry is removed."""
        try:
            data = await self._supervisor_client.discovery.get(UUID(uuid))
        except SupervisorError as err:
            _LOGGER.debug("Can't read discovery data: %s", err)
        else:
            await self.async_process_new(data)

    async def async_process_new(self, data: Discovery) -> None:
        """Process add discovery entry."""
        # Read additional Add-on info
        try:
            addon_info = await self._supervisor_client.addons.addon_info(data.addon)
        except SupervisorError as err:
            _LOGGER.error("Can't read add-on info: %s", err)
            return

        data.config[ATTR_ADDON] = addon_info.name

        # Use config flow
        discovery_flow.async_create_flow(
            self.hass,
            data.service,
            context={"source": config_entries.SOURCE_HASSIO},
            data=HassioServiceInfo(
                config=data.config,
                name=addon_info.name,
                slug=data.addon,
                uuid=data.uuid.hex,
            ),
            discovery_key=discovery_flow.DiscoveryKey(
                domain=DOMAIN,
                key=data.uuid.hex,
                version=1,
            ),
        )

    async def async_process_del(self, data: dict[str, Any]) -> None:
        """Process remove discovery entry."""
        service: str = data[ATTR_SERVICE]
        uuid: str = data[ATTR_UUID]

        # Check if really deletet / prevent injections
        try:
            await self._supervisor_client.discovery.get(UUID(uuid))
        except SupervisorError:
            pass
        else:
            _LOGGER.warning("Retrieve wrong unload for %s", service)
            return

        # Use config flow
        for entry in self.hass.config_entries.async_entries(service):
            if entry.source != config_entries.SOURCE_HASSIO or entry.unique_id != uuid:
                continue
            await self.hass.config_entries.async_remove(entry.entry_id)
