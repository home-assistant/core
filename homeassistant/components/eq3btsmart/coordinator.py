"""Coordinator for the eq3btsmart integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

from eq3btsmart import Thermostat
from eq3btsmart.exceptions import Eq3Exception

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    RECONNECT_INTERVAL,
    SCAN_INTERVAL,
    SIGNAL_THERMOSTAT_CONNECTED,
    SIGNAL_THERMOSTAT_DISCONNECTED,
)

_LOGGER = logging.getLogger(__name__)

type Eq3ConfigEntry = ConfigEntry[Eq3ConfigEntryData]


@dataclass(slots=True)
class Eq3ConfigEntryData:
    """Config entry for a single eQ-3 device."""

    thermostat: Thermostat
    coordinator: Eq3Coordinator


class Eq3Coordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for the eq3btsmart integration."""

    config_entry: Eq3ConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: Eq3ConfigEntry, mac_address: str
    ) -> None:
        """Initialize the coordinator."""

        super().__init__(
            hass,
            _LOGGER,
            name=format_mac(mac_address),
            update_interval=timedelta(seconds=SCAN_INTERVAL),
            config_entry=entry,
            always_update=True,
        )

        self._mac_address = mac_address

    async def _async_setup(self) -> None:
        """Connect to the thermostat."""

        self.config_entry.runtime_data.thermostat.register_update_callback(
            self._async_on_update_received
        )

        await self._async_reconnect_thermostat()

    async def async_shutdown(self) -> None:
        """Disconnect from the thermostat."""

        self.config_entry.runtime_data.thermostat.unregister_update_callback(
            self._async_on_update_received
        )

        await super().async_shutdown()

    async def _async_update_data(self) -> dict[str, Any]:
        """Request status update from thermostat."""

        try:
            await self.config_entry.runtime_data.thermostat.async_get_status()
        except Eq3Exception as e:
            if not self.config_entry.runtime_data.thermostat.is_connected:
                _LOGGER.error(
                    "[%s] eQ-3 device disconnected",
                    self._mac_address,
                )
                async_dispatcher_send(
                    self.hass,
                    f"{SIGNAL_THERMOSTAT_DISCONNECTED}_{self._mac_address}",
                )
                await self._async_reconnect_thermostat()
                return {}

            raise UpdateFailed(f"Error updating eQ-3 device: {e}") from e

        return {}

    async def _async_reconnect_thermostat(self) -> None:
        """Reconnect the thermostat."""

        while True:
            try:
                await self.config_entry.runtime_data.thermostat.async_connect()
            except Eq3Exception:
                await asyncio.sleep(RECONNECT_INTERVAL)
                continue

            _LOGGER.debug(
                "[%s] eQ-3 device connected",
                self._mac_address,
            )

            async_dispatcher_send(
                self.hass,
                f"{SIGNAL_THERMOSTAT_CONNECTED}_{self._mac_address}",
            )

            return

    def _async_on_update_received(self) -> None:
        """Handle updated data from the thermostat."""

        self.async_set_updated_data({})
