"""The Coordinator for EnergyZero."""

from datetime import timedelta
from typing import NamedTuple, override
from zoneinfo import ZoneInfo

from energyzero import (
    EnergyPrices,
    EnergyZero,
    EnergyZeroConnectionError,
    EnergyZeroNoDataError,
    PriceType,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ELECTRICITY_PRICE_INTERVAL,
    DEFAULT_ELECTRICITY_PRICE_INTERVAL,
    DOMAIN,
    ELECTRICITY_INTERVALS,
    LOGGER,
    SCAN_INTERVAL,
    THRESHOLD_HOUR,
)

type EnergyZeroConfigEntry = ConfigEntry[EnergyZeroDataUpdateCoordinator]


class EnergyZeroData(NamedTuple):
    """Class for defining data in dict."""

    energy_today: EnergyPrices
    energy_tomorrow: EnergyPrices | None
    gas_today: EnergyPrices | None
    electricity_price_step: timedelta

    @property
    def next_energy_price(self) -> float | None:
        """Return the electricity price one market period from now."""
        return self.energy_today.price_at_time(
            self.energy_today.utcnow() + self.electricity_price_step
        )


class EnergyZeroDataUpdateCoordinator(DataUpdateCoordinator[EnergyZeroData]):
    """Class to manage fetching EnergyZero data from single endpoint."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: EnergyZeroConfigEntry) -> None:
        """Initialize global EnergyZero data updater."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
            config_entry=entry,
        )

        interval = entry.options.get(
            CONF_ELECTRICITY_PRICE_INTERVAL, DEFAULT_ELECTRICITY_PRICE_INTERVAL
        )
        self.electricity_interval = ELECTRICITY_INTERVALS[interval]
        self.electricity_price_step = timedelta(
            minutes=15 if interval == "quarter_hourly" else 60
        )
        self.energyzero = EnergyZero(session=async_get_clientsession(hass))

    @override
    async def _async_update_data(self) -> EnergyZeroData:
        """Fetch data from EnergyZero."""
        today = dt_util.now().date()
        gas_today = None
        energy_tomorrow = None
        local_tz = ZoneInfo(self.hass.config.time_zone)

        try:
            energy_today = await self.energyzero.get_electricity_prices(
                start_date=today,
                end_date=today,
                interval=self.electricity_interval,
                price_type=PriceType.MARKET_WITH_VAT,
                local_tz=local_tz,
            )
            try:
                gas_today = await self.energyzero.get_gas_prices(
                    start_date=today,
                    end_date=today,
                    price_type=PriceType.MARKET_WITH_VAT,
                    local_tz=local_tz,
                )
            except EnergyZeroNoDataError:
                LOGGER.debug("No data for gas prices for EnergyZero integration")
            # Energy for tomorrow only after 14:00 UTC
            if dt_util.utcnow().hour >= THRESHOLD_HOUR:
                tomorrow = today + timedelta(days=1)
                try:
                    energy_tomorrow = await self.energyzero.get_electricity_prices(
                        start_date=tomorrow,
                        end_date=tomorrow,
                        interval=self.electricity_interval,
                        price_type=PriceType.MARKET_WITH_VAT,
                        local_tz=local_tz,
                    )
                except EnergyZeroNoDataError:
                    LOGGER.debug("No data for tomorrow for EnergyZero integration")

        except EnergyZeroConnectionError as err:
            raise UpdateFailed("Error communicating with EnergyZero API") from err

        return EnergyZeroData(
            energy_today=energy_today,
            energy_tomorrow=energy_tomorrow,
            gas_today=gas_today,
            electricity_price_step=self.electricity_price_step,
        )
