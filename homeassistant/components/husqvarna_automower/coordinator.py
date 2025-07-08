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
        self._areas_in_register: dict[str, set[int]] = {}

    def _async_add_remove_devices_and_entities(self, data: MowerDictionary) -> None:
        """Add/remove devices and dynamic entities, when amount of devices changed."""
        self._async_add_remove_devices(data)
        for mower_id in data:
            if data[mower_id].capabilities.stay_out_zones:
                self._async_add_remove_stay_out_zones(data)
            if data[mower_id].capabilities.work_areas:
                self._async_add_remove_work_areas(data)

    async def _async_update_data(self) -> MowerDictionary:
        """Subscribe for websocket and poll data from the API."""
        if not self.ws_connected:
            await self.api.connect()
            self.api.register_data_callback(self.handle_websocket_updates)
            self.ws_connected = True
        try:
            data = await self.api.get_status()
        except ApiError as err:
            raise UpdateFailed(err) from err
        except AuthError as err:
            raise ConfigEntryAuthFailed(err) from err
        self._async_add_remove_devices_and_entities(data)
        return data

    @callback
    def handle_websocket_updates(self, ws_data: MowerDictionary) -> None:
        """Process websocket callbacks and write them to the DataUpdateCoordinator."""
        self.hass.async_create_task(self._process_websocket_update(ws_data))

    async def _process_websocket_update(self, ws_data: MowerDictionary) -> None:
        """Handle incoming websocket update and update coordinator data."""
        for data in ws_data.values():
            existing_areas = data.work_areas or {}
            for task in data.calendar.tasks:
                work_area_id = task.work_area_id
                if work_area_id is not None and work_area_id not in existing_areas:
                    _LOGGER.debug(
                        "New work area %s detected, refreshing data", work_area_id
                    )
                    await self.async_refresh()
                    return

        self.async_set_updated_data(ws_data)
        self._async_add_remove_devices_and_entities(ws_data)

    @callback
    def async_set_updated_data(self, data: MowerDictionary) -> None:
        """Override DataUpdateCoordinator to preserve fixed polling interval.

        The built-in implementation resets the polling timer on every websocket
        update. Since websockets do not deliver all required data (e.g. statistics
        or work area details), we enforce a constant REST polling cadence.
        """
        self.data = data
        self.last_update_success = True
        self.logger.debug(
            "Manually updated %s data",
            self.name,
        )
        self.async_update_listeners()

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
            self.data = data
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

        entity_registry = er.async_get(self.hass)

        registered_zones: dict[str, set[str]] = {}
        for mower_id in data:
            registered_zones[mower_id] = set()
            for entity_entry in er.async_entries_for_config_entry(
                entity_registry, self.config_entry.entry_id
            ):
                uid = entity_entry.unique_id
                if uid.startswith(f"{mower_id}_") and uid.endswith("_stay_out_zones"):
                    zone_id = uid.removeprefix(f"{mower_id}_").removesuffix(
                        "_stay_out_zones"
                    )
                    registered_zones[mower_id].add(zone_id)

        for mower_id, current_ids in current_zones.items():
            known_ids = registered_zones.get(mower_id, set())

            new_zones = current_ids - known_ids
            removed_zones = known_ids - current_ids

            if new_zones:
                for zone_callback in self.new_zones_callbacks:
                    zone_callback(mower_id, new_zones)

            for entity_entry in er.async_entries_for_config_entry(
                entity_registry, self.config_entry.entry_id
            ):
                for zone_id in removed_zones:
                    if entity_entry.unique_id == f"{mower_id}_{zone_id}_stay_out_zones":
                        entity_registry.async_remove(entity_entry.entity_id)

    def _async_add_remove_work_areas(self, data: MowerDictionary) -> None:
        """Add new work areas, remove non-existing work areas."""
        current_areas = {
            mower_id: set(mower_data.work_areas)
            for mower_id, mower_data in data.items()
            if mower_data.capabilities.work_areas and mower_data.work_areas is not None
        }

        if not self._areas_in_register:
            entity_registry = er.async_get(self.hass)
            self._areas_in_register = {}

            for mower_id in self.data:
                self._areas_in_register[mower_id] = set()
                for entity_entry in er.async_entries_for_config_entry(
                    entity_registry, self.config_entry.entry_id
                ):
                    if entity_entry.unique_id.startswith(
                        mower_id
                    ) and entity_entry.unique_id.endswith("work_area"):
                        work_area_id = entity_entry.unique_id.removeprefix(
                            f"{mower_id}_"
                        ).split("_")[0]
                        self._areas_in_register[mower_id].add(int(work_area_id))

        for mower_id, current_ids in current_areas.items():
            previous_ids = self._areas_in_register.get(mower_id, set())
            new_areas = current_ids - previous_ids
            removed_areas = previous_ids - current_ids

            if new_areas:
                self.data = data
                for area_callback in self.new_areas_callbacks:
                    area_callback(mower_id, new_areas)

            entity_registry = er.async_get(self.hass)
            for entity_entry in er.async_entries_for_config_entry(
                entity_registry, self.config_entry.entry_id
            ):
                for area in removed_areas:
                    if entity_entry.unique_id.startswith(f"{mower_id}_{area}_"):
                        entity_registry.async_remove(entity_entry.entity_id)

        self._areas_in_register = current_areas
