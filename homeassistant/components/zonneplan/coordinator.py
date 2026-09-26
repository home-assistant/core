"""Coordinator for Zonneplan."""

import asyncio
from dataclasses import dataclass
from datetime import date, timedelta
import logging
from typing import TYPE_CHECKING, override

from pyzonneplan import (
    Account,
    Connection,
    ConsumerPrices,
    ElectricityChart,
    GasChart,
    Zonneplan,
    ZonneplanAuthenticationError,
    ZonneplanConnectionError,
    ZonneplanTimeoutError,
)
from pyzonneplan.const import ConsumptionChart, PriceChart

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN

LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(minutes=15)

type ZonneplanConfigEntry = ConfigEntry[ZonneplanCoordinator]


@dataclass(frozen=True, kw_only=True)
class ZonneplanData:
    """Data fetched by the Zonneplan coordinator."""

    account: Account
    electricity_prices: ConsumerPrices | None = None
    gas_prices: ConsumerPrices | None = None
    electricity_usage: ElectricityChart | None = None
    gas_usage: GasChart | None = None


def _connection(account: Account, market_segment: str) -> Connection | None:
    """Return the first connection of a market segment, if the account has one."""
    return next(
        (
            connection
            for connection in account.connections
            if connection.market_segment is not None
            and market_segment in connection.market_segment
        ),
        None,
    )


class ZonneplanCoordinator(DataUpdateCoordinator[ZonneplanData]):
    """Coordinator to manage fetching Zonneplan account data."""

    config_entry: ZonneplanConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: ZonneplanConfigEntry, zonneplan: Zonneplan
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.zonneplan = zonneplan

    async def _async_fetch_electricity(
        self, account: Account, today: date
    ) -> tuple[ConsumerPrices | None, ElectricityChart | None]:
        """Fetch electricity prices and usage, if the account has electricity."""
        if (connection := _connection(account, "electricity")) is None:
            return None, None
        return await asyncio.gather(
            self.zonneplan.async_get_consumer_prices(PriceChart.ELECTRICITY_HOURLY),
            self.zonneplan.async_get_electricity_chart(
                connection.uuid, today, ConsumptionChart.DAYS
            ),
        )

    async def _async_fetch_gas(
        self, account: Account, today: date
    ) -> tuple[ConsumerPrices | None, GasChart | None]:
        """Fetch gas prices and usage, if the account has gas."""
        if (connection := _connection(account, "gas")) is None:
            return None, None
        return await asyncio.gather(
            self.zonneplan.async_get_consumer_prices(PriceChart.GAS_DAILY),
            self.zonneplan.async_get_gas_chart(
                connection.uuid, today, ConsumptionChart.DAYS
            ),
        )

    @override
    async def _async_update_data(self) -> ZonneplanData:
        """Fetch data from the Zonneplan API."""
        try:
            account = await self.zonneplan.async_get_account()
            # The consumption charts cover the month of the given local day.
            today = dt_util.now().date()
            (
                (electricity_prices, electricity_usage),
                (gas_prices, gas_usage),
            ) = await asyncio.gather(
                self._async_fetch_electricity(account, today),
                self._async_fetch_gas(account, today),
            )
        except ZonneplanAuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
            ) from err
        except ZonneplanTimeoutError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="timeout_connect",
            ) from err
        except ZonneplanConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from err

        if TYPE_CHECKING:
            assert self.zonneplan.token is not None

        token = self.zonneplan.token.as_dict()
        if self.config_entry.data.get(CONF_TOKEN) != token:
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={**self.config_entry.data, CONF_TOKEN: token},
            )

        return ZonneplanData(
            account=account,
            electricity_prices=electricity_prices,
            gas_prices=gas_prices,
            electricity_usage=electricity_usage,
            gas_usage=gas_usage,
        )
