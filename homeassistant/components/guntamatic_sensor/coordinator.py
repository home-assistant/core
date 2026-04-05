"""Coordinator for Guntamatic integration."""

from __future__ import annotations

import logging

from guntamatic.heater import Heater

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class GuntamaticCoordinator(DataUpdateCoordinator[dict[str, list[str]]]):
    """Guntamatic data coordinator."""

    def __init__(self, hass: HomeAssistant, heater: Heater, entry: ConfigEntry) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
            config_entry=entry,
        )
        self.heater = heater

    async def _async_update_data(self) -> dict[str, list[str]]:
        """Fetch data from heater.

        Expected return format:
            {
                "Boiler Temperature": [68.5, "°C"],
                "Flue Temperature": [115.2, "°C"],
                "Power Output": [12.4, "kW"],
            }

        """
        try:
            data: dict[str, list[str]] = await self.hass.async_add_executor_job(
                self.heater.get_data
            )
        except Exception as err:
            raise UpdateFailed(f"Error communicating with heater: {err}") from err
        if not data:
            raise UpdateFailed("No data received from heater")
        if not data.get("Serial"):
            raise UpdateFailed("Could not get serial number from heater")
        return data
