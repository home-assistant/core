# AirQCoordinator example
"""Data update coordinator for Tilt Pi."""

from datetime import timedelta
import logging

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .model import TiltColor, TiltHydrometerData

_LOGGER = logging.getLogger(__name__)
DEFAULT_SCAN_INTERVAL = timedelta(seconds=10)

type TiltPiConfigEntry = ConfigEntry[TiltPiDataUpdateCoordinator]


class TiltPiDataUpdateCoordinator(DataUpdateCoordinator[list[TiltHydrometerData]]):
    """Class to manage fetching Tilt Pi data."""

    config_entry: TiltPiConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: TiltPiConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name="Tilt Pi",
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self._host = config_entry.data[CONF_HOST]
        self._port = config_entry.data[CONF_PORT]
        self._session = async_get_clientsession(hass)
        self.identifier = config_entry.entry_id

    async def _async_update_data(self) -> list[TiltHydrometerData]:
        """Fetch data from Tilt Pi."""
        try:
            async with self._session.get(
                f"http://{self._host}:{self._port}/macid/all",
                timeout=aiohttp.ClientTimeout(10),
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
        except (TimeoutError, aiohttp.ClientError) as err:
            raise UpdateFailed(f"Error communicating with Tilt Pi: {err}") from err

        return [
            TiltHydrometerData(
                mac_id=hydrometer["mac"],
                color=TiltColor(hydrometer["Color"].title()),
                temperature=float(hydrometer["Temp"]),
                gravity=float(hydrometer["SG"]),
            )
            for hydrometer in data
        ]
