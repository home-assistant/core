"""Coordinator for Arcam FMJ integration."""

from __future__ import annotations

import logging

from arcam.fmj import ConnectionFailed
from arcam.fmj.client import Client
from arcam.fmj.state import State

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


class ArcamFmjCoordinator(DataUpdateCoordinator[State]):
    """Coordinator for a single Arcam FMJ zone."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        client: Client,
        zone: int,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"Arcam FMJ zone {zone}",
        )
        self.client = client
        self.state = State(client, zone)
        self.last_update_success = False

    async def _async_initial_update(self) -> None:
        """Perform initial state update after connection is established."""
        try:
            await self.state.update()
        except ConnectionFailed:
            _LOGGER.debug(
                "Connection lost during initial update for zone %s", self.state.zn
            )
            self.last_update_success = False
            self.async_update_listeners()
        else:
            self.last_update_success = True
            self.async_set_updated_data(self.state)

    async def _async_update_data(self) -> State:
        """Fetch data for manual refresh."""
        try:
            await self.state.update()
        except ConnectionFailed as err:
            raise UpdateFailed(
                f"Connection failed during update for zone {self.state.zn}"
            ) from err
        return self.state

    @callback
    def async_notify_data_updated(self) -> None:
        """Notify that new data has been received from the device."""
        self.async_set_updated_data(self.state)

    @callback
    def async_notify_connected(self) -> None:
        """Handle client connected."""
        self.hass.async_create_task(self._async_initial_update())

    @callback
    def async_notify_disconnected(self) -> None:
        """Handle client disconnected."""
        self.last_update_success = False
        self.async_update_listeners()
