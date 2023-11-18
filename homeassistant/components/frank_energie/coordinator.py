"""Coordinator implementation for Frank Energie integration."""
from __future__ import annotations

from datetime import date, timedelta
import logging
from typing import TypedDict

from python_frank_energie import FrankEnergie
from python_frank_energie.exceptions import AuthException, RequestException
from python_frank_energie.models import Invoices, MarketPrices, MonthSummary, PriceData

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import CONF_AUTH_TOKEN, CONF_REFRESH_TOKEN, DeviceResponseEntry

LOGGER = logging.getLogger(__name__)


class FrankEnergieData(TypedDict):
    """Frank Energie data."""

    DATA_ELECTRICITY: PriceData
    DATA_GAS: PriceData
    DATA_MONTH_SUMMARY: MonthSummary | None
    DATA_INVOICES: Invoices | None


class FrankEnergieCoordinator(DataUpdateCoordinator[DeviceResponseEntry]):
    """Get the latest data and update the states."""

    api: FrankEnergie

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, api: FrankEnergie
    ) -> None:
        """Initialize the data object."""
        self.hass = hass
        self.entry = entry
        self.api = api

        super().__init__(
            hass,
            LOGGER,
            name="Frank Energie coordinator",
            update_interval=timedelta(minutes=60),
        )

    async def _async_update_data(self) -> DeviceResponseEntry:
        """Get the latest data from Frank Energie."""
        LOGGER.debug("Fetching Frank Energie data")

        # We request data for today up until the day after tomorrow.
        # This is to ensure we always request all available data.
        today = dt_util.utcnow().date()
        tomorrow = today + timedelta(days=1)
        day_after_tomorrow = today + timedelta(days=2)

        ## Token expires after 7 days, so we renew it if it's expired
        if self.api.is_authenticated and not self.api.authentication_valid():
            await self.__try_renew_token()

        # Fetch data for today and tomorrow separately,
        # because the gas prices response only contains data for the first day of the query
        try:
            prices_today = await self.__fetch_prices_with_fallback(today, tomorrow)
            prices_tomorrow = await self.__fetch_prices_with_fallback(
                tomorrow, day_after_tomorrow
            )

            data_month_summary = (
                await self.api.month_summary() if self.api.is_authenticated else None
            )
            data_invoices = (
                await self.api.invoices() if self.api.is_authenticated else None
            )
        except RequestException as ex:
            if str(ex).startswith("user-error:"):
                raise ConfigEntryAuthFailed from ex

            raise UpdateFailed(ex) from ex

        return DeviceResponseEntry(
            electricity=prices_today.electricity + prices_tomorrow.electricity,
            gas=prices_today.gas + prices_tomorrow.gas,
            month_summary=data_month_summary,
            invoices=data_invoices,
        )

    async def __fetch_prices_with_fallback(
        self, start_date: date, end_date: date
    ) -> MarketPrices:
        if not self.api.is_authenticated:
            return await self.api.prices(start_date, end_date)

        user_prices = await self.api.user_prices(start_date)

        if len(user_prices.gas.all) > 0 and len(user_prices.electricity.all) > 0:
            # If user_prices are available for both gas and electricity return them
            return user_prices

        public_prices = await self.api.prices(start_date, end_date)

        # Use public prices if no user prices are available
        if len(user_prices.gas.all) == 0:
            LOGGER.info("No gas prices found for user, falling back to public prices")
            user_prices.gas = public_prices.gas

        if len(user_prices.electricity.all) == 0:
            LOGGER.info(
                "No electricity prices found for user, falling back to public prices"
            )
            user_prices.electricity = public_prices.electricity

        return user_prices

    async def __try_renew_token(self):
        try:
            updated_tokens = await self.api.renew_token()

            data = {
                CONF_AUTH_TOKEN: updated_tokens.authToken,
                CONF_REFRESH_TOKEN: updated_tokens.refreshToken,
            }
            self.hass.config_entries.async_update_entry(self.entry, data=data)

            LOGGER.debug("Successfully renewed token")

        except AuthException as ex:
            raise ConfigEntryError("Failed to renew token") from ex
