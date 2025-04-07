"""The GIOS component."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging

from aiohttp.client_exceptions import ClientConnectorError
from gios import Gios
from gios.exceptions import GiosError
from gios.model import GiosSensors

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import API_TIMEOUT, DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

type GiosConfigEntry = ConfigEntry[GiosData]


@dataclass
class GiosData:
    """Data for GIOS integration."""

    coordinator: GiosDataUpdateCoordinator


class GiosDataUpdateCoordinator(DataUpdateCoordinator[GiosSensors]):
    """Define an object to hold GIOS data."""

    config_entry: GiosConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: GiosConfigEntry,
        gios: Gios,
    ) -> None:
        """Class to manage fetching GIOS data API."""
        self.gios = gios

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> GiosSensors:
        """Update data via library."""
        try:
            async with asyncio.timeout(API_TIMEOUT):
                return await self.gios.async_update()
        except (GiosError, ClientConnectorError) as error:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_error",
                translation_placeholders={
                    "entry": self.config_entry.title,
                    "error": repr(error),
                },
            ) from error
