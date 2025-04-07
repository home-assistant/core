"""Data UpdateCoordinator for the Husqvarna Automower integration."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import timedelta
import logging

from aioautomower.exceptions import (
    ApiError,
    AuthError,
    HusqvarnaTimeoutError,
    HusqvarnaWSServerHandshakeError,
)
from aioautomower.model import MowerDictionary
from aioautomower.session import AutomowerSession

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
MAX_WS_RECONNECT_TIME = 600
SCAN_INTERVAL = timedelta(minutes=8)
DEFAULT_RECONNECT_TIME = 2  # Define a default reconnect time

type AutomowerConfigEntry = ConfigEntry[AutomowerDataUpdateCoordinator]


class AutomowerDataUpdateCoordinator(DataUpdateCoordinator[MowerDictionary]):
    """Class to manage fetching Husqvarna data."""

    config_entry: AutomowerConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: AutomowerConfigEntry,
        api: AutomowerSession,
    ) -> None:
        """Initialize data updater."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.api = api
        self.ws_connected: bool = False
        self.reconnect_time = DEFAULT_RECONNECT_TIME
        self.new_devices_callbacks: list[Callable[[set[str]], None]] = []
        self.new_zones_callbacks: list[Callable[[str, set[str]], None]] = []
        self.new_areas_callbacks: list[Callable[[str, set[int]], None]] = []
        self._devices_last_update: set[str] = set()
        self._zones_last_update: dict[str, set[str]] = {}
        self._areas_last_update: dict[str, set[int]] = {}

    async def _async_update_data(self) -> MowerDictionary:
        """Subscribe for websocket and poll data from the API."""
        if not self.ws_connected:
            await self.api.connect()
            self.api.register_data_callback(self.callback)
            self.ws_connected = True
        try:
            data = await self.api.get_status()
        except ApiError as err:
            raise UpdateFailed(err) from err
        except AuthError as err:
            raise ConfigEntryAuthFailed(err) from err

        self._async_add_remove_devices(data)
        for mower_id in data:
            if data[mower_id].capabilities.stay_out_zones:
                self._async_add_remove_stay_out_zones(data)
        for mower_id in data:
            if data[mower_id].capabilities.work_areas:
                self._async_add_remove_work_areas(data)
        return data

    @callback
    def callback(self, ws_data: MowerDictionary) -> None:
        """Process websocket callbacks and write them to the DataUpdateCoordinator."""
        self.async_set_updated_data(ws_data)

    async def client_listen(
        self,
        hass: HomeAssistant,
        entry: AutomowerConfigEntry,
        automower_client: AutomowerSession,
    ) -> None:
        """Listen with the client."""
        try:
            await automower_client.auth.websocket_connect()
            # Reset reconnect time after successful connection
            self.reconnect_time = DEFAULT_RECONNECT_TIME
            await automower_client.start_listening()
        except HusqvarnaWSServerHandshakeError as err:
            _LOGGER.debug(
                "Failed to connect to websocket. Trying to reconnect: %s",
                err,
            )
        except HusqvarnaTimeoutError as err:
            _LOGGER.debug(
                "Failed to listen to websocket. Trying to reconnect: %s",
                err,
            )
        if not hass.is_stopping:
            await asyncio.sleep(self.reconnect_time)
            self.reconnect_time = min(self.reconnect_time * 2, MAX_WS_RECONNECT_TIME)
            entry.async_create_background_task(
                hass,
                self.client_listen(hass, entry, automower_client),
                "reconnect_task",
            )

    def _async_add_remove_devices(self, data: MowerDictionary) -> None:
        """Add new device, remove non-existing device."""
        current_devices = set(data)

        # Skip update if no changes
        if current_devices == self._devices_last_update:
            return

        # Process removed devices
        removed_devices = self._devices_last_update - current_devices
        if removed_devices:
            _LOGGER.debug("Removed devices: %s", ", ".join(map(str, removed_devices)))
            self._remove_device(removed_devices)

        # Process new device
        new_devices = current_devices - self._devices_last_update
        if new_devices:
            _LOGGER.debug("New devices found: %s", ", ".join(map(str, new_devices)))
            self._add_new_devices(new_devices)

        # Update device state
        self._devices_last_update = current_devices

    def _remove_device(self, removed_devices: set[str]) -> None:
        """Remove device from the registry."""
        device_registry = dr.async_get(self.hass)
        for mower_id in removed_devices:
            if device := device_registry.async_get_device(
                identifiers={(DOMAIN, str(mower_id))}
            ):
                device_registry.async_update_device(
                    device_id=device.id,
                    remove_config_entry_id=self.config_entry.entry_id,
                )

    def _add_new_devices(self, new_devices: set[str]) -> None:
        """Add new device and trigger callbacks."""
        for mower_callback in self.new_devices_callbacks:
            mower_callback(new_devices)

    def _async_add_remove_stay_out_zones(self, data: MowerDictionary) -> None:
        """Add new stay-out zones, remove non-existing stay-out zones."""
        current_zones = {
            mower_id: set(mower_data.stay_out_zones.zones)
            for mower_id, mower_data in data.items()
            if mower_data.capabilities.stay_out_zones
            and mower_data.stay_out_zones is not None
        }

        if not self._zones_last_update:
            self._zones_last_update = current_zones
            return

        if current_zones == self._zones_last_update:
            return

        self._zones_last_update = self._update_stay_out_zones(current_zones)

    def _update_stay_out_zones(
        self, current_zones: dict[str, set[str]]
    ) -> dict[str, set[str]]:
        """Update stay-out zones by adding and removing as needed."""
        new_zones = {
            mower_id: zones - self._zones_last_update.get(mower_id, set())
            for mower_id, zones in current_zones.items()
        }
        removed_zones = {
            mower_id: self._zones_last_update.get(mower_id, set()) - zones
            for mower_id, zones in current_zones.items()
        }

        for mower_id, zones in new_zones.items():
            for zone_callback in self.new_zones_callbacks:
                zone_callback(mower_id, set(zones))

        entity_registry = er.async_get(self.hass)
        for mower_id, zones in removed_zones.items():
            for entity_entry in er.async_entries_for_config_entry(
                entity_registry, self.config_entry.entry_id
            ):
                for zone in zones:
                    if entity_entry.unique_id.startswith(f"{mower_id}_{zone}"):
                        entity_registry.async_remove(entity_entry.entity_id)

        return current_zones

    def _async_add_remove_work_areas(self, data: MowerDictionary) -> None:
        """Add new work areas, remove non-existing work areas."""
        current_areas = {
            mower_id: set(mower_data.work_areas)
            for mower_id, mower_data in data.items()
            if mower_data.capabilities.work_areas and mower_data.work_areas is not None
        }

        if not self._areas_last_update:
            self._areas_last_update = current_areas
            return

        if current_areas == self._areas_last_update:
            return

        self._areas_last_update = self._update_work_areas(current_areas)

    def _update_work_areas(
        self, current_areas: dict[str, set[int]]
    ) -> dict[str, set[int]]:
        """Update work areas by adding and removing as needed."""
        new_areas = {
            mower_id: areas - self._areas_last_update.get(mower_id, set())
            for mower_id, areas in current_areas.items()
        }
        removed_areas = {
            mower_id: self._areas_last_update.get(mower_id, set()) - areas
            for mower_id, areas in current_areas.items()
        }

        for mower_id, areas in new_areas.items():
            for area_callback in self.new_areas_callbacks:
                area_callback(mower_id, set(areas))

        entity_registry = er.async_get(self.hass)
        for mower_id, areas in removed_areas.items():
            for entity_entry in er.async_entries_for_config_entry(
                entity_registry, self.config_entry.entry_id
            ):
                for area in areas:
                    if entity_entry.unique_id.startswith(f"{mower_id}_{area}_"):
                        entity_registry.async_remove(entity_entry.entity_id)

        return current_areas
