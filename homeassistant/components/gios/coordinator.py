"""The GIOS component."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING

from aiohttp.client_exceptions import ClientConnectorError
from gios import Gios
from gios.exceptions import GiosError
from gios.model import GiosSensors

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import API_TIMEOUT, DOMAIN, MANUFACTURER, SCAN_INTERVAL, URL

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

        station_id = gios.station_id
        if TYPE_CHECKING:
            # Station ID is Optional in the library, but here we know it is set for sure
            # so we can safely assert it is not None for type checking purposes
            # Gios instance is created only with a valid station ID in the async_setup_entry.
            assert station_id is not None

        self.device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, str(station_id))},
            manufacturer=MANUFACTURER,
            name=config_entry.data[CONF_NAME],
            configuration_url=URL.format(station_id=station_id),
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
