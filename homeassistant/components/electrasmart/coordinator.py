"""Coordinator for the Electra Air Conditioner integration."""

import asyncio
from datetime import timedelta
import logging
import time
from typing import override

from electrasmart.api import ElectraAPI, ElectraApiError
from electrasmart.device import ElectraAirConditioner

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import API_DELAY, DOMAIN, SCAN_INTERVAL_SEC

_LOGGER = logging.getLogger(__name__)

type ElectraSmartConfigEntry = ConfigEntry[ElectraSmartCoordinator]


class ElectraSmartCoordinator(DataUpdateCoordinator[None]):
    """Poll the telemetry of every AC on the account.

    The library keeps the fetched state on the device objects themselves, so
    the coordinator fetches the telemetry and the entities read their state
    from the device they belong to.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ElectraSmartConfigEntry,
        api: ElectraAPI,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL_SEC),
        )
        self.api = api
        self._skip_until: dict[str, float] = {}
        self._consecutive_failures: dict[str, int] = {}

    @override
    async def _async_update_data(self) -> None:
        """Fetch the state of every AC.

        A failed poll keeps the last known state instead of marking the
        entities unavailable: this cloud API answers with errors often enough
        that an AC is reported as unavailable only once its telemetry stops
        arriving for UNAVAILABLE_THRESH_SEC.
        """
        now = time.monotonic()
        await asyncio.gather(
            *(
                self._async_fetch_telemetry(device)
                for device in self.api.devices
                if now >= self._skip_until.get(device.mac, 0)
            )
        )

    async def _async_fetch_telemetry(self, device: ElectraAirConditioner) -> None:
        """Fetch the telemetry of a single AC."""
        try:
            await self.api.get_last_telemtry(device)
        except ElectraApiError as err:
            self._consecutive_failures[device.mac] = (
                self._consecutive_failures.get(device.mac, 0) + 1
            )
            _LOGGER.warning(
                "Failed to get %s (%s) state: %s"
                " (try #%i since last success), keeping the last known state",
                device.name,
                device.mac,
                err,
                self._consecutive_failures[device.mac],
            )
            return

        self._consecutive_failures.pop(device.mac, None)

    def async_command_sent(self, mac: str) -> None:
        """Keep the state a command just set, as the API lags behind it."""
        self._skip_until[mac] = time.monotonic() + API_DELAY
