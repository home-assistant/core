"""Data UpdateCoordinator for the Husqvarna Automower integration."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta
import logging
from typing import override

from aioautomower.exceptions import (
    ApiError,
    AuthError,
    HusqvarnaTimeoutError,
    HusqvarnaWSClientError,
    HusqvarnaWSServerHandshakeError,
)
from aioautomower.model import MowerDictionary, MowerStates
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
PING_INTERVAL = 60

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
        self.reconnect_time = DEFAULT_RECONNECT_TIME
        self.new_devices_callbacks: list[Callable[[set[str]], None]] = []
        self.new_zones_callbacks: list[Callable[[str, set[str]], None]] = []
        self.new_areas_callbacks: list[Callable[[str, set[int]], None]] = []
        self.pong: datetime | None = None
        self.websocket_alive: bool = False
        self.websocket_callbacks: list[Callable[[bool], None]] = []
        self._watchdog_task: asyncio.Task | None = None

    @override
    @callback
    def async_update_listeners(self) -> None:
        self._on_data_update()
        super().async_update_listeners()

    async def _async_setup(self) -> None:
        """Initialize websocket connection and callbacks."""
        await self.api.connect()
        self.api.register_data_callback(self.handle_websocket_updates)

        def start_watchdog() -> None:
            if self._watchdog_task is not None and not self._watchdog_task.done():
                _LOGGER.debug("Cancelling previous watchdog task")
                self._watchdog_task.cancel()
            self._watchdog_task = self.config_entry.async_create_background_task(
                self.hass,
                self._pong_watchdog(),
                "websocket_watchdog",
            )

        self.api.register_ws_ready_callback(start_watchdog)

    async def _async_update_data(self) -> MowerDictionary:
        """Poll data from the API."""
        try:
            return await self.api.get_status()
        except ApiError as err:
            raise UpdateFailed(err) from err
        except AuthError as err:
            raise ConfigEntryAuthFailed(err) from err

    @callback
    def _on_data_update(self) -> None:
        """Handle data updates and process dynamic entity management."""
        if self.data is not None:
            self._async_add_remove_devices()
            if any(
                mower_data.capabilities.stay_out_zones
                for mower_data in self.data.values()
            ):
                self._async_add_remove_stay_out_zones()
            if any(
                mower_data.capabilities.work_areas for mower_data in self.data.values()
            ):
                self._async_add_remove_work_areas()
            if (
                not self._should_poll()
                and self.update_interval is not None
                and self.websocket_alive
            ):
                _LOGGER.debug("All mowers inactive and websocket alive: stop polling")
                self.update_interval = None
            if self.update_interval is None and self._should_poll():
                _LOGGER.debug(
                    "Polling re-enabled via WebSocket: at least one mower active"
                )
                self.update_interval = SCAN_INTERVAL
                self.hass.async_create_task(self.async_request_refresh())

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
                    await self.async_request_refresh()
                    return

        self.async_set_updated_data(ws_data)

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
        except (HusqvarnaWSServerHandshakeError, HusqvarnaWSClientError) as err:
            _LOGGER.debug(
                "Failed to connect to websocket. Trying to reconnect: %s",
                err,
            )
        except HusqvarnaTimeoutError as err:
            _LOGGER.debug(
                "Failed to listen to websocket. Trying to reconnect: %s",
                err,
            )

    def _should_poll(self) -> bool:
        """Return True if at least one mower is connected and at least one is not OFF."""
        return any(mower.metadata.connected for mower in self.data.values()) and any(
            mower.mower.state != MowerStates.OFF for mower in self.data.values()
        )

    async def _pong_watchdog(self) -> None:
        """Watchdog to check for pong messages."""
        _LOGGER.debug("Watchdog started")
        try:
            while True:
                _LOGGER.debug("Sending ping")
                is_alive = await self.api.send_empty_message()
                _LOGGER.debug("Ping result: %s", is_alive)
                if self.websocket_alive != is_alive:
                    self.websocket_alive = is_alive
                    for ws_callback in self.websocket_callbacks:
                        ws_callback(is_alive)

                await asyncio.sleep(PING_INTERVAL)
                _LOGGER.debug("Websocket alive %s", self.websocket_alive)
                if not self.websocket_alive:
                    _LOGGER.debug("No pong received → restart polling")
                    if self.update_interval is None:
                        self.update_interval = SCAN_INTERVAL
                        await self.async_request_refresh()
        except asyncio.CancelledError:
            _LOGGER.debug("Watchdog cancelled")

    def _async_add_remove_devices(self) -> None:
        """Add new devices and remove orphaned devices from the registry."""
        current_devices = set(self.data)
        device_registry = dr.async_get(self.hass)

        registered_devices: set[str] = {
            str(mower_id)
            for device in device_registry.devices.get_devices_for_config_entry_id(
                self.config_entry.entry_id
            )
            for domain, mower_id in device.identifiers
            if domain == DOMAIN
        }

        orphaned_devices = registered_devices - current_devices
        if orphaned_devices:
            _LOGGER.debug("Removing orphaned devices: %s", orphaned_devices)
            device_registry = dr.async_get(self.hass)
            for mower_id in orphaned_devices:
                dev = device_registry.async_get_device(identifiers={(DOMAIN, mower_id)})
                if dev is not None:
                    device_registry.async_update_device(
                        device_id=dev.id,
                        remove_config_entry_id=self.config_entry.entry_id,
                    )

        new_devices = current_devices - registered_devices
        if new_devices:
            _LOGGER.debug("New devices found: %s", new_devices)
            for mower_callback in self.new_devices_callbacks:
                mower_callback(new_devices)

    def _async_add_remove_stay_out_zones(self) -> None:
        """Add new stay-out zones, remove non-existing stay-out zones."""
        current_zones = {
            mower_id: set(mower_data.stay_out_zones.zones)
            for mower_id, mower_data in self.data.items()
            if mower_data.capabilities.stay_out_zones
            and mower_data.stay_out_zones is not None
        }

        entity_registry = er.async_get(self.hass)
        entries = er.async_entries_for_config_entry(
            entity_registry, self.config_entry.entry_id
        )

        registered_zones: dict[str, set[str]] = {}
        for mower_id in self.data:
            registered_zones[mower_id] = set()
            for entry in entries:
                uid = entry.unique_id
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
                _LOGGER.debug("New stay-out zones: %s", new_zones)
                for zone_callback in self.new_zones_callbacks:
                    zone_callback(mower_id, new_zones)

            if removed_zones:
                _LOGGER.debug("Removing stay-out zones: %s", removed_zones)
                for entry in entries:
                    for zone_id in removed_zones:
                        if entry.unique_id == f"{mower_id}_{zone_id}_stay_out_zones":
                            entity_registry.async_remove(entry.entity_id)

    def _async_add_remove_work_areas(self) -> None:
        """Add new work areas, remove non-existing work areas."""
        current_areas = {
            mower_id: set(mower_data.work_areas)
            for mower_id, mower_data in self.data.items()
            if mower_data.capabilities.work_areas and mower_data.work_areas is not None
        }

        entity_registry = er.async_get(self.hass)
        entries = er.async_entries_for_config_entry(
            entity_registry, self.config_entry.entry_id
        )

        registered_areas: dict[str, set[int]] = {}
        for mower_id in self.data:
            registered_areas[mower_id] = set()
            for entry in entries:
                uid = entry.unique_id
                if uid.startswith(f"{mower_id}_") and uid.endswith("_work_area"):
                    parts = uid.removeprefix(f"{mower_id}_").split("_")
                    area_id_str = parts[0] if parts else None
                    if area_id_str and area_id_str.isdigit():
                        registered_areas[mower_id].add(int(area_id_str))

        for mower_id, current_ids in current_areas.items():
            known_ids = registered_areas.get(mower_id, set())

            new_areas = current_ids - known_ids
            removed_areas = known_ids - current_ids

            if new_areas:
                _LOGGER.debug("New work areas: %s", new_areas)
                for area_callback in self.new_areas_callbacks:
                    area_callback(mower_id, new_areas)

            if removed_areas:
                _LOGGER.debug("Removing work areas: %s", removed_areas)
                for entry in entries:
                    for area_id in removed_areas:
                        if entry.unique_id.startswith(f"{mower_id}_{area_id}_"):
                            entity_registry.async_remove(entry.entity_id)
