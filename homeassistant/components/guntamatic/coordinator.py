"""Coordinator for Guntamatic integration."""

import logging

from guntamatic.heater import Heater
import requests

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

type GuntamaticConfigEntry = ConfigEntry[GuntamaticCoordinator]


class GuntamaticCoordinator(DataUpdateCoordinator[dict[str, list[str]]]):
    """Guntamatic data coordinator."""

    def __init__(self, hass: HomeAssistant, entry: GuntamaticConfigEntry) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
            config_entry=entry,
        )
        self.heater = Heater(entry.data[CONF_HOST])

    async def _async_update_data(self) -> dict[str, list[str]]:
        """Fetch data from heater."""
        try:
            data: dict[str, list[str]] = await self.hass.async_add_executor_job(
                self.heater.parse_data
            )
        except requests.exceptions.ConnectionError as err:
            raise UpdateFailed(f"Cannot connect to heater: {err}") from err
        return data
