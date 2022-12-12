"""The Coordinator for EnergyZero."""
from __future__ import annotations

from datetime import timedelta
from typing import TypedDict

from energyzero import Electricity, EnergyZero, EnergyZeroNoDataError, Gas

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt

from .const import (
    CONF_GAS,
    DOMAIN,
    LOGGER,
    SCAN_INTERVAL,
    SERVICE_ENERGY_TODAY,
    SERVICE_ENERGY_TOMORROW,
    SERVICE_GAS_TODAY,
    THRESHOLD_HOUR,
)


class EnergyZeroData(TypedDict):
    """Class for defining data in dict."""

    energy_today: Electricity
    energy_tomorrow: Electricity | None
    gas_today: Gas | None


class EnergyZeroDataUpdateCoordinator(DataUpdateCoordinator[EnergyZeroData]):
    """Class to manage fetching EnergyZero data from single endpoint."""

    config_entry: ConfigEntry
    has_tomorrow_data: bool | None = None

    def __init__(self, hass) -> None:
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
        today = dt.now().replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow = today + timedelta(days=1)
        data: EnergyZeroData = {
            SERVICE_ENERGY_TODAY: await self.energyzero.energy_prices(
                start_date=today, end_date=today
            ),
            SERVICE_ENERGY_TOMORROW: None,
            SERVICE_GAS_TODAY: None,
        }

        # Gas for today - optional in config flow
        if self.config_entry.data.get(CONF_GAS):
            data[SERVICE_GAS_TODAY] = await self.energyzero.gas_prices(
                start_date=today, end_date=today
            )

        # Energy for tomorrow only after 14:00
        if dt.now().hour >= THRESHOLD_HOUR and (
            self.has_tomorrow_data or self.has_tomorrow_data is None
        ):
            try:
                data[SERVICE_ENERGY_TOMORROW] = await self.energyzero.energy_prices(
                    start_date=tomorrow, end_date=tomorrow
                )
                self.has_tomorrow_data = True
            except EnergyZeroNoDataError:
                LOGGER.debug("No data for tomorrow for EnergyZero integration")
                if self.has_tomorrow_data is None:
                    self.has_tomorrow_data = False

        return data
