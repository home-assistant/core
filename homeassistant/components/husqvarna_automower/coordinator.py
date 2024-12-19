"""Data UpdateCoordinator for the Husqvarna Automower integration."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import timedelta
import logging
from typing import TYPE_CHECKING

from aioautomower.exceptions import (
    ApiException,
    AuthException,
    HusqvarnaWSServerHandshakeError,
    TimeoutException,
)
from aioautomower.model import MowerAttributes
from aioautomower.session import AutomowerSession

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

if TYPE_CHECKING:
    from . import AutomowerConfigEntry

_LOGGER = logging.getLogger(__name__)
MAX_WS_RECONNECT_TIME = 600
SCAN_INTERVAL = timedelta(minutes=8)
DEFAULT_RECONNECT_TIME = 2  # Define a default reconnect time


class AutomowerDataUpdateCoordinator(DataUpdateCoordinator[dict[str, MowerAttributes]]):
    """Class to manage fetching Husqvarna data."""

    config_entry: AutomowerConfigEntry

    def __init__(self, hass: HomeAssistant, api: AutomowerSession) -> None:
        """Initialize data updater."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.api = api
        self.ws_connected: bool = False
        self.reconnect_time = DEFAULT_RECONNECT_TIME
        self.new_lock_callbacks: list[Callable[[str], None]] = []
        self.new_zones_callbacks: list[Callable[[str, set[str]], None]] = []
        self._locks_last_update: set[str] = set()
        self._zones_last_update: dict[str, set[str]] = {}

    async def _async_update_data(self) -> dict[str, MowerAttributes]:
        """Subscribe for websocket and poll data from the API."""
        if not self.ws_connected:
            await self.api.connect()
            self.api.register_data_callback(self.callback)
            self.ws_connected = True
        try:
            self.data = await self.api.get_status()
        except ApiException as err:
            raise UpdateFailed(err) from err
        except AuthException as err:
            raise ConfigEntryAuthFailed(err) from err

        self._async_add_remove_locks()
        for mower_id in self.data:
            if self.data[mower_id].capabilities.stay_out_zones:
                self._async_add_remove_stay_out_zones()
        return self.data

    @callback
    def callback(self, ws_data: dict[str, MowerAttributes]) -> None:
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
        except TimeoutException as err:
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

    def _async_add_remove_locks(self) -> None:
        """Add new locks, remove non-existing locks."""
        current_locks = set(self.data)

        # Skip update if no changes
        if current_locks == self._locks_last_update:
            return

        # Process removed locks
        removed_locks = self._locks_last_update - current_locks
        if removed_locks:
            _LOGGER.debug("Removed locks: %s", ", ".join(map(str, removed_locks)))
            self._remove_locks(removed_locks)

        # Process new locks
        new_locks = current_locks - self._locks_last_update
        if new_locks:
            _LOGGER.debug("New locks found: %s", ", ".join(map(str, new_locks)))
            self._add_new_locks(new_locks)

        # Update lock state
        self._locks_last_update = current_locks

    def _remove_locks(self, removed_locks: set[str]) -> None:
        """Remove locks from the registry."""
        device_registry = dr.async_get(self.hass)
        for lock_id in removed_locks:
            if device := device_registry.async_get_device(
                identifiers={(DOMAIN, str(lock_id))}
            ):
                device_registry.async_update_device(
                    device_id=device.id,
                    remove_config_entry_id=self.config_entry.entry_id,
                )

    def _add_new_locks(self, new_locks: set[str]) -> None:
        """Add new locks and trigger callbacks."""
        for lock_id in new_locks:
            for mower_callback in self.new_lock_callbacks:
                mower_callback(lock_id)

    def _async_add_remove_stay_out_zones(self) -> None:
        """Add new stay-out zones, remove non-existing stay-out zones."""
        current_zones = {
            mower_id: set(mower_data.stay_out_zones.zones)
            for mower_id, mower_data in self.data.items()
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
