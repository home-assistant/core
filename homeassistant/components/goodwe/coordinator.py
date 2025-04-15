"""Update coordinator for Goodwe."""

from __future__ import annotations

import logging
from typing import Any

from goodwe import Inverter, InverterError, RequestFailedException

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class GoodweUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Gather data for the energy device."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        inverter: Inverter,
    ) -> None:
        """Initialize update coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=entry.title,
            update_interval=SCAN_INTERVAL,
        )
        self.inverter: Inverter = inverter
        self._last_data: dict[str, Any] = {}

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the inverter."""
        try:
            self._last_data = self.data if self.data else {}
            return await self.inverter.read_runtime_data()
        except RequestFailedException as ex:
            # UDP communication with inverter is by definition unreliable.
            # It is rather normal in many environments to fail to receive
            # proper response in usual time, so we intentionally ignore isolated
            # failures and report problem with availability only after
            # consecutive streak of 3 of failed requests.
            if ex.consecutive_failures_count < 3:
                _LOGGER.debug(
                    "No response received (streak of %d)", ex.consecutive_failures_count
                )
                # return last known data
                return self._last_data
            # Inverter does not respond anymore (e.g. it went to sleep mode)
            _LOGGER.debug(
                "Inverter not responding (streak of %d)", ex.consecutive_failures_count
            )
            raise UpdateFailed(ex) from ex
        except InverterError as ex:
            raise UpdateFailed(ex) from ex

    def sensor_value(self, sensor: str) -> Any:
        """Answer current (or last known) value of the sensor."""
        val = self.data.get(sensor)
        return val if val is not None else self._last_data.get(sensor)

    def total_sensor_value(self, sensor: str) -> Any:
        """Answer current value of the 'total' (never 0) sensor."""
        val = self.data.get(sensor)
        return val if val else self._last_data.get(sensor)

    def reset_sensor(self, sensor: str) -> None:
        """Reset sensor value to 0.

        Intended for "daily" cumulative sensors (e.g. PV energy produced today),
        which should be explicitly reset to 0 at midnight if inverter is suspended.
        """
        self._last_data[sensor] = 0
        self.data[sensor] = 0
