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
        self._confirmed_macs: set[str] = set()

    @override
    async def _async_update_data(self) -> None:
        """Fetch the state of every AC.

        A failed poll keeps the last known state instead of marking the
        entities unavailable: this cloud API answers with errors often enough
        that an AC is reported as unavailable only once its telemetry stops
        arriving for UNAVAILABLE_THRESH_SEC.
        """
        now = time.monotonic()
        # Only the ACs this refresh fetched carry a state the cloud confirmed,
        # so the ACs whose polls are paused and the ones that fail to answer
        # are collected afresh on every refresh.
        self._confirmed_macs = set()
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
        self._confirmed_macs.add(device.mac)

    def last_refresh_confirmed(self, mac: str) -> bool:
        """Return whether the refresh that just ran confirmed this AC's state.

        An AC is confirmed when the refresh fetched its telemetry and the
        cloud answered. One whose polls are paused, because the API still
        serves the state from before a command, and one whose fetch failed
        both keep the state they already had, which is the state a command
        left behind when the cloud did not accept it. The entities use this to
        decide whether they may publish the state the device object carries.
        """
        return mac in self._confirmed_macs

    def async_command_sent(self, mac: str) -> None:
        """Keep the state a command just set, as the API lags behind it."""
        self._skip_until[mac] = time.monotonic() + API_DELAY
