"""The Coordinator for EnergyZero."""
from __future__ import annotations

from datetime import timedelta
from typing import Literal, NamedTuple

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
from homeassistant.helpers.template import Template
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN, LOGGER, SCAN_INTERVAL, THRESHOLD_HOUR


class EnergyZeroData(NamedTuple):
    """Class for defining data in dict."""

    energy: Electricity
    energy_today: Electricity
    energy_tomorrow: Electricity | None
    gas: Gas | None


class EnergyZeroDataUpdateCoordinator(DataUpdateCoordinator[EnergyZeroData]):
    """Class to manage fetching EnergyZero data from single endpoint."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        gas_modifyer: Literal,
        energy_modifyer: Literal,
    ) -> None:
        """Initialize global EnergyZero data updater."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

        self.gas_modifyer = Template(gas_modifyer, hass)
        self.energy_modifyer = Template(energy_modifyer, hass)

        self.energyzero = EnergyZero(
            session=async_get_clientsession(hass),
            incl_btw="false",
        )

    async def _async_update_data(self) -> EnergyZeroData:
        """Fetch data from EnergyZero."""
        today = dt_util.now().date()
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
            if dt_util.utcnow().hour >= THRESHOLD_HOUR:
                tomorrow = today + timedelta(days=1)
                try:
                    energy_tomorrow = await self.energyzero.energy_prices(
                        start_date=tomorrow, end_date=tomorrow
                    )
                except EnergyZeroNoDataError:
                    LOGGER.debug("No data for tomorrow for EnergyZero integration")

        except EnergyZeroConnectionError as err:
            raise UpdateFailed("Error communicating with EnergyZero API") from err

        energy_today.prices = self._apply_template(
            self.energy_modifyer, energy_today.prices
        )

        if energy_tomorrow is not None:
            energy_tomorrow.prices = self._apply_template(
                self.energy_modifyer, energy_tomorrow.prices
            )

        energy_all = Electricity(
            prices=energy_today.prices
            | (energy_tomorrow.prices if energy_tomorrow is not None else {})
        )
        if gas_today is not None:
            gas_today.prices = self._apply_template(self.gas_modifyer, gas_today.prices)

        return EnergyZeroData(
            energy=energy_all,
            energy_today=energy_today,
            energy_tomorrow=energy_tomorrow,
            gas=gas_today,
        )

    def _apply_template(
        self, template: Template, prices: dict[str, float]
    ) -> dict[str, float]:
        return {
            key: template.async_render(price=value) for key, value in prices.items()
        }
