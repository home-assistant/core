"""Coordinator for the Kii Audio integration."""

import asyncio
import copy
import logging
from typing import Any

from aiohttp import ClientSession
from aiokii import KiiAudioClient, KiiAudioError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

type KiiAudioConfigEntry = ConfigEntry[KiiAudioCoordinator]


class KiiAudioCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinate Kii Audio system state."""

    config_entry: KiiAudioConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: KiiAudioConfigEntry,
        session: ClientSession,
    ) -> None:
        """Initialize the coordinator."""
        self._ready = asyncio.Event()
        self.client = KiiAudioClient(session, config_entry.data[CONF_HOST])
        self.client.add_listener(self._handle_event)
        self.client.add_connection_listener(self._handle_connection_state)

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
        )

    async def async_wait_ready(self) -> None:
        """Wait for initial system information from the WebSocket."""
        async with asyncio.timeout(10):
            await self._ready.wait()

    async def async_set_zone_setting(
        self, zone_id: str, setting: str, value: Any
    ) -> None:
        """Request a zone setting change."""
        await self.client.set_zone_setting(zone_id, setting, value)

    async def async_set_zone_volume(self, zone_id: str, volume: float) -> None:
        """Request a zone volume change."""
        await self.async_set_zone_setting(zone_id, "audio.volume", volume)

    async def async_set_zone_mute(self, zone_id: str, mute: bool) -> None:
        """Request a zone mute change."""
        await self.async_set_zone_setting(zone_id, "audio.mute", mute)

    async def async_set_zone_power(self, zone_id: str, power: bool) -> None:
        """Request a zone power change."""
        await self.async_set_zone_setting(zone_id, "power", power)

    async def async_set_zone_source(self, zone_id: str, source: str) -> None:
        """Request a zone source change."""
        await self.async_set_zone_setting(zone_id, "audio.source", source)

    @callback
    def _handle_connection_state(self, connected: bool) -> None:
        """Handle WebSocket connection state changes."""
        if connected:
            if self.data is not None:
                self.async_set_updated_data(self.data)
            return
        if not self._ready.is_set():
            return
        self.async_set_update_error(KiiAudioError("WebSocket disconnected"))

    @callback
    def _handle_event(self, event: str, payload: dict[str, Any]) -> None:
        """Handle a pushed WebSocket event."""
        if event == "pushSystemInfo":
            self.async_set_updated_data(payload)
            self._ready.set()
            return

        if event == "pushZoneSetting":
            self._handle_zone_setting(payload)

    @callback
    def _handle_zone_setting(self, payload: dict[str, Any]) -> None:
        """Apply a pushed zone setting update to the cached system info."""
        zone_id = payload["zoneId"]
        setting = payload["setting"]
        value = payload["value"]

        current_data = self.data
        zones = current_data["zones"]

        for index, zone in enumerate(zones):
            if zone["zoneId"] != zone_id:
                continue
            settings = zone["settings"]

            data = dict(current_data)
            zones_copy = list(zones)
            zone_copy = dict(zone)
            settings_copy = copy.deepcopy(settings)
            zone_copy["settings"] = settings_copy
            zones_copy[index] = zone_copy
            data["zones"] = zones_copy

            _set_path(settings_copy, setting, value)
            if "updateCount" in payload:
                settings_copy["updateCount"] = payload["updateCount"]
            self.async_set_updated_data(data)
            return


def _set_path(target: dict[str, Any], path: str, value: Any) -> None:
    """Set a dotted path in a nested dictionary."""
    parts = path.split(".")
    current = target
    for part in parts[:-1]:
        next_value = current.setdefault(part, {})
        if not isinstance(next_value, dict):
            next_value = {}
            current[part] = next_value
        current = next_value
    current[parts[-1]] = value
