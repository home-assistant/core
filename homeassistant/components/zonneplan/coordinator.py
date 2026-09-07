"""Coordinator for Zonneplan."""

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import TYPE_CHECKING, override

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

            # Depending per contract, fetch the associated consumer prices
            for connection in account.connections:
                if (
                    "electricity" in connection.market_segment
                    if connection.market_segment is not None
                    else False
                ):
                    electricity_prices = await self.zonneplan.async_get_consumer_prices(
                        PriceChart.ELECTRICITY_HOURLY
                    )
                if (
                    "gas" in connection.market_segment
                    if connection.market_segment is not None
                    else False
                ):
                    gas_prices = await self.zonneplan.async_get_consumer_prices(
                        PriceChart.GAS_DAILY
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
        )
