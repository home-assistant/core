"""The Coordinator for EnergyZero."""
from __future__ import annotations

from datetime import timedelta
from typing import NamedTuple

from energyzero import (
    Electricity,
    EnergyZero,
    EnergyZeroConnectionError,
    EnergyZeroNoDataError,
    Gas,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt

from .const import DOMAIN, LOGGER, SCAN_INTERVAL, THRESHOLD_HOUR


class EnergyZeroData(NamedTuple):
    """Class for defining data in dict."""

    energy_today: Electricity
    energy_tomorrow: Electricity | None
    gas_today: Gas | None


class EnergyZeroDataUpdateCoordinator(DataUpdateCoordinator[EnergyZeroData]):
    """Class to manage fetching EnergyZero data from single endpoint."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize global EnergyZero data updater."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

        self.energyzero = EnergyZero(session=async_get_clientsession(hass))

    async def _async_update_data(self) -> EnergyZeroData:
        """Fetch data from EnergyZero."""
        today = dt.now().date()
        gas_today = None
        energy_tomorrow = None

        try:
            energy_today = await self.energyzero.energy_prices(
                start_date=today, end_date=today
            )
            try:
                gas_today = await self.energyzero.gas_prices(
                    start_date=today, end_date=today
                )
            except EnergyZeroNoDataError:
                LOGGER.debug("No data for gas prices for EnergyZero integration")
            # Energy for tomorrow only after 14:00 UTC
            if dt.utcnow().hour >= THRESHOLD_HOUR:
                tomorrow = today + timedelta(days=1)
                try:
                    energy_tomorrow = await self.energyzero.energy_prices(
                        start_date=tomorrow, end_date=tomorrow
                    )
                except EnergyZeroNoDataError:
                    LOGGER.debug("No data for tomorrow for EnergyZero integration")

        except EnergyZeroConnectionError as err:
            raise UpdateFailed("Error communicating with EnergyZero API") from err

        return EnergyZeroData(
            energy_today=energy_today,
            energy_tomorrow=energy_tomorrow,
            gas_today=gas_today,
        )
