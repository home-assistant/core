"""The Coordinator for EnergyZero."""

from datetime import date, timedelta
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

    electricity_market_today: EnergyPrices
    electricity_market_tomorrow: EnergyPrices | None
    electricity_all_in_today: EnergyPrices
    electricity_all_in_tomorrow: EnergyPrices | None
    gas_today: EnergyPrices | None
    electricity_price_step: timedelta

    def next_price(self, prices: EnergyPrices) -> float | None:
        """Return the price one configured electricity period from now."""
        return prices.price_at_time(prices.utcnow() + self.electricity_price_step)


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

    async def _async_get_electricity_prices(
        self,
        day: date,
        local_tz: ZoneInfo,
        *,
        allow_partial: bool = False,
    ) -> dict[PriceType, EnergyPrices]:
        """Fetch both price streams, optionally retaining a partially published day."""
        price_types = (PriceType.MARKET_WITH_VAT, PriceType.ALL_IN)
        try:
            return await self.energyzero.get_electricity_prices(
                start_date=day,
                end_date=day,
                interval=self.electricity_interval,
                price_type=price_types,
                local_tz=local_tz,
            )
        except EnergyZeroNoDataError:
            if not allow_partial:
                raise

        # The library cannot return a partial multi-stream response.
        electricity = {}
        for price_type in price_types:
            try:
                prices = await self.energyzero.get_electricity_prices(
                    start_date=day,
                    end_date=day,
                    interval=self.electricity_interval,
                    price_type=price_type,
                    local_tz=local_tz,
                )
            except EnergyZeroNoDataError:
                LOGGER.debug("No %s electricity prices for %s", price_type, day)
            else:
                electricity[price_type] = prices
        return electricity

    @override
    async def _async_update_data(self) -> EnergyZeroData:
        """Fetch data from EnergyZero."""
        today = dt_util.now().date()
        gas_today = None
        electricity_tomorrow: dict[PriceType, EnergyPrices] = {}
        local_tz = ZoneInfo(self.hass.config.time_zone)

        try:
            electricity_today = await self._async_get_electricity_prices(
                today, local_tz
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
                electricity_tomorrow = await self._async_get_electricity_prices(
                    today + timedelta(days=1), local_tz, allow_partial=True
                )
        except EnergyZeroConnectionError as err:
            raise UpdateFailed("Error communicating with EnergyZero API") from err

        return EnergyZeroData(
            electricity_market_today=electricity_today[PriceType.MARKET_WITH_VAT],
            electricity_market_tomorrow=electricity_tomorrow.get(
                PriceType.MARKET_WITH_VAT
            ),
            electricity_all_in_today=electricity_today[PriceType.ALL_IN],
            electricity_all_in_tomorrow=electricity_tomorrow.get(PriceType.ALL_IN),
            gas_today=gas_today,
            electricity_price_step=self.electricity_price_step,
        )
