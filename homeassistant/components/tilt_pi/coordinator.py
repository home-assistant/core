# AirQCoordinator example
"""Data update coordinator for Tilt Pi."""

from datetime import timedelta
import logging

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .model import TiltColor, TiltHydrometerData

_LOGGER = logging.getLogger(__name__)


class TiltPiDataUpdateCoordinator(DataUpdateCoordinator[list[TiltHydrometerData]]):
    """Class to manage fetching Tilt Pi data."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Tilt Pi",
            update_interval=timedelta(seconds=30),
        )
        self.config_entry = entry
        self._host = entry.data[CONF_HOST]
        self._session = async_get_clientsession(hass)

    async def _async_update_data(self) -> list[TiltHydrometerData]:
        """Fetch data from Tilt Pi."""
        try:
            async with self._session.get(
                f"http://{self._host}/macid/all", timeout=aiohttp.ClientTimeout(10)
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
        except (TimeoutError, aiohttp.ClientError) as err:
            raise UpdateFailed(f"Error communicating with Tilt Pi: {err}") from err

        return [
            TiltHydrometerData(
                mac_id=hydrometer["mac"],
                color=TiltColor(hydrometer["Color"].lower()),
                temperature=float(hydrometer["Temp"]),
                gravity=float(hydrometer["SG"]),
            )
            for hydrometer in data
        ]
