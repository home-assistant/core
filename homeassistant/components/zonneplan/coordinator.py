"""Coordinator for Zonneplan."""

import asyncio
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
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(minutes=15)

type ZonneplanConfigEntry = ConfigEntry[ZonneplanCoordinator]


@dataclass(frozen=True, kw_only=True)
class ZonneplanData:
    """Data fetched by the Zonneplan coordinator."""

    account: Account
    electricity_prices: ConsumerPrices
    gas_prices: ConsumerPrices


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
            account, electricity_prices, gas_prices = await asyncio.gather(
                self.zonneplan.async_get_account(),
                self.zonneplan.async_get_consumer_prices(PriceChart.ELECTRICITY_HOURLY),
                self.zonneplan.async_get_consumer_prices(PriceChart.GAS_DAILY),
            )
        except ZonneplanAuthenticationError as err:
            raise UpdateFailed(
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

        self._async_persist_token()

        return ZonneplanData(
            account=account,
            electricity_prices=electricity_prices,
            gas_prices=gas_prices,
        )

    def _async_persist_token(self) -> None:
        """Persist a rotated refresh token to the config entry."""
        if TYPE_CHECKING:
            assert self.zonneplan.token is not None

        token = self.zonneplan.token.as_dict()
        if self.config_entry.data.get(CONF_TOKEN) != token:
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={**self.config_entry.data, CONF_TOKEN: token},
            )
