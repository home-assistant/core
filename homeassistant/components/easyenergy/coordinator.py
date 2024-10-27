"""The Coordinator for easyEnergy."""

from __future__ import annotations

from datetime import timedelta
from typing import NamedTuple

from easyenergy import (
    EasyEnergy,
    EasyEnergyConnectionError,
    EasyEnergyNoDataError,
    Electricity,
    Gas,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN, LOGGER, SCAN_INTERVAL, THRESHOLD_HOUR


class EasyEnergyData(NamedTuple):
    """Class for defining data in dict."""

    energy_today: Electricity
    energy_tomorrow: Electricity | None
    gas_today: Gas | None


class EasyEnergyDataUpdateCoordinator(DataUpdateCoordinator[EasyEnergyData]):
    """Class to manage fetching easyEnergy data from single endpoint."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize global easyEnergy data updater."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

        self.easyenergy = EasyEnergy(session=async_get_clientsession(hass))

    async def _async_update_data(self) -> EasyEnergyData:
        """Fetch data from easyEnergy."""
        today = dt_util.now().date()
        gas_today = None
        energy_tomorrow = None

        try:
            energy_today = await self.easyenergy.energy_prices(
                start_date=today, end_date=today
            )
            try:
                gas_today = await self.easyenergy.gas_prices(
                    start_date=today, end_date=today
                )
            except EasyEnergyNoDataError:
                LOGGER.debug("No data for gas prices for easyEnergy integration")
            # Energy for tomorrow only after 14:00 UTC
            if dt_util.utcnow().hour >= THRESHOLD_HOUR:
                tomorrow = today + timedelta(days=1)
                try:
                    energy_tomorrow = await self.easyenergy.energy_prices(
                        start_date=tomorrow, end_date=tomorrow
                    )
                except EasyEnergyNoDataError:
                    LOGGER.debug(
                        "No electricity data for tomorrow for easyEnergy integration"
                    )

        except EasyEnergyConnectionError as err:
            raise UpdateFailed("Error communicating with easyEnergy API") from err

        return EasyEnergyData(
            energy_today=energy_today,
            energy_tomorrow=energy_tomorrow,
            gas_today=gas_today,
        )
