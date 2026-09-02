"""Coordinator for Zonneplan."""

import asyncio
from collections.abc import Coroutine
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import TYPE_CHECKING, Any, override

from pyzonneplan import (
    Account,
    ConsumerPrices,
    Zonneplan,
    ZonneplanAuthenticationError,
    ZonneplanConnectionError,
    ZonneplanTimeoutError,
)
from pyzonneplan.const import PriceChart

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

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

    @override
    async def _async_update_data(self) -> ZonneplanData:
        """Fetch data from the Zonneplan API."""
        try:
            account = await self.zonneplan.async_get_account()
            electricity_prices: ConsumerPrices | None = None
            gas_prices: ConsumerPrices | None = None
            price_coroutines: dict[str, Coroutine[Any, Any, ConsumerPrices]] = {}

            if any(
                connection.market_segment is not None
                and "electricity" in connection.market_segment
                for connection in account.connections
            ):
                price_coroutines["electricity"] = (
                    self.zonneplan.async_get_consumer_prices(
                        PriceChart.ELECTRICITY_HOURLY
                    )
                )
            if any(
                connection.market_segment is not None
                and "gas" in connection.market_segment
                for connection in account.connections
            ):
                price_coroutines["gas"] = self.zonneplan.async_get_consumer_prices(
                    PriceChart.GAS_DAILY
                )

            prices = dict(
                zip(
                    price_coroutines,
                    await asyncio.gather(*price_coroutines.values()),
                    strict=True,
                )
            )
            electricity_prices = prices.get("electricity")
            gas_prices = prices.get("gas")
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
        )
