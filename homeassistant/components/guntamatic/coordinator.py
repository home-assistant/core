"""Coordinator for Guntamatic integration."""

from __future__ import annotations

import logging

from guntamatic.heater import Heater, NoSerialException
import requests

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

type GuntamaticConfigEntry = ConfigEntry[GuntamaticCoordinator]


class GuntamaticCoordinator(DataUpdateCoordinator[dict[str, list[str]]]):
    """Guntamatic data coordinator."""

    def __init__(
        self, hass: HomeAssistant, heater: Heater, entry: GuntamaticConfigEntry
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
            config_entry=entry,
        )
        self.heater = heater

    async def _async_setup(self) -> None:
        """Do initialization logic."""
        try:
            await self.hass.async_add_executor_job(self.heater.parse_data)
        except NoSerialException as err:
            raise ConfigEntryError(f"Unexpected data from heater: {err}") from err
        except requests.exceptions.ConnectionError as err:
            raise ConfigEntryNotReady(f"Cannot connect to heater: {err}") from err

    async def _async_update_data(self) -> dict[str, list[str]]:
        """Fetch data from heater."""
        try:
            data: dict[str, list[str]] = await self.hass.async_add_executor_job(
                self.heater.parse_data
            )
        except requests.exceptions.ConnectionError as err:
            raise UpdateFailed(f"Cannot connect to heater: {err}") from err
        return data
