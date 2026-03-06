"""Coordinator for the kraken integration."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

import krakenex
import pykrakenapi

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_TRACKED_ASSET_PAIRS,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TRACKED_ASSET_PAIR,
    DOMAIN,
    KrakenResponse,
)
from .utils import get_tradable_asset_pairs

CALL_RATE_LIMIT_SLEEP = 1

_LOGGER = logging.getLogger(__name__)


class KrakenData:
    """Define an object to hold kraken data."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize."""
        self._hass = hass
        self._config_entry = config_entry
        self._api = pykrakenapi.KrakenAPI(krakenex.API(), retry=0, crl_sleep=0)
        self.tradable_asset_pairs: dict[str, str] = {}
        self.coordinator: DataUpdateCoordinator[KrakenResponse | None] | None = None

    async def async_update(self) -> KrakenResponse | None:
        """Get the latest data from the Kraken.com REST API.

        All tradeable asset pairs are retrieved, not the tracked asset pairs
        selected by the user. This enables us to check for an unknown and
        thus likely removed asset pair in sensor.py and only log a warning
        once.
        """
        try:
            async with asyncio.timeout(10):
                return await self._hass.async_add_executor_job(self._get_kraken_data)
        except pykrakenapi.pykrakenapi.KrakenAPIError as error:
            if "Unknown asset pair" in str(error):
                _LOGGER.warning(
                    "Kraken.com reported an unknown asset pair. Refreshing list of"
                    " tradable asset pairs"
                )
                await self._async_refresh_tradable_asset_pairs()
            else:
                raise UpdateFailed(
                    f"Unable to fetch data from Kraken.com: {error}"
                ) from error
        except pykrakenapi.pykrakenapi.CallRateLimitError:
            _LOGGER.warning(
                "Exceeded the Kraken.com call rate limit. Increase the update interval"
                " to prevent this error"
            )
        return None

    def _get_kraken_data(self) -> KrakenResponse:
        websocket_name_pairs = self._get_websocket_name_asset_pairs()
        ticker_df = self._api.get_ticker_information(websocket_name_pairs)
        # Rename columns to their full name
        ticker_df = ticker_df.rename(
            columns={
                "a": "ask",
                "b": "bid",
                "c": "last_trade_closed",
                "v": "volume",
                "p": "volume_weighted_average",
                "t": "number_of_trades",
                "l": "low",
                "h": "high",
                "o": "opening_price",
            }
        )
        response_dict: KrakenResponse = ticker_df.transpose().to_dict()
        return response_dict

    async def _async_refresh_tradable_asset_pairs(self) -> None:
        self.tradable_asset_pairs = await self._hass.async_add_executor_job(
            get_tradable_asset_pairs, self._api
        )

    async def async_setup(self) -> None:
        """Set up the Kraken integration."""
        if not self._config_entry.options:
            options = {
                CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                CONF_TRACKED_ASSET_PAIRS: [DEFAULT_TRACKED_ASSET_PAIR],
            }
            self._hass.config_entries.async_update_entry(
                self._config_entry, options=options
            )
        await self._async_refresh_tradable_asset_pairs()
        # Wait 1 second to avoid triggering the KrakenAPI CallRateLimiter
        await asyncio.sleep(CALL_RATE_LIMIT_SLEEP)
        self.coordinator = DataUpdateCoordinator(
            self._hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=self._config_entry,
            update_method=self.async_update,
            update_interval=timedelta(
                seconds=self._config_entry.options[CONF_SCAN_INTERVAL]
            ),
        )
        await self.coordinator.async_config_entry_first_refresh()
        # Wait 1 second to avoid triggering the KrakenAPI CallRateLimiter
        await asyncio.sleep(CALL_RATE_LIMIT_SLEEP)

    def _get_websocket_name_asset_pairs(self) -> str:
        return ",".join(
            pair
            for tracked_pair in self._config_entry.options[CONF_TRACKED_ASSET_PAIRS]
            if (pair := self.tradable_asset_pairs.get(tracked_pair)) is not None
        )

    def set_update_interval(self, update_interval: int) -> None:
        """Set the coordinator update_interval to the supplied update_interval."""
        if self.coordinator is not None:
            self.coordinator.update_interval = timedelta(seconds=update_interval)
