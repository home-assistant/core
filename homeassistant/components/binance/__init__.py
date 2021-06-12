"""Gather the market details from Binance."""
from __future__ import annotations

import asyncio
import logging

from binance import AsyncClient
from binance.exceptions import BinanceAPIException, BinanceRequestException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    ASSET_VALUE_BASE,
    ASSET_VALUE_CURRENCIES,
    CONF_API_SECRET,
    CONF_MARKETS,
    DOMAIN,
    PLATFORMS,
    SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Binance from a config entry."""
    api_key = entry.data[CONF_API_KEY]
    api_secret = entry.data[CONF_API_SECRET]
    markets = entry.data[CONF_MARKETS]

    coordinator = BinanceDataUpdateCoordinator(hass, api_key, api_secret, markets)
    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Binance config entry."""

    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )

    if unload_ok:
        del hass.data[DOMAIN][entry.entry_id]

    return unload_ok


class BinanceDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to get the latest data from Binance."""

    def __init__(
        self, hass, api_key, api_secret, markets, balances: list | None = None
    ):
        """Initialize the data object."""
        self._api_key = api_key
        self._api_secret = api_secret

        self.markets = markets
        self.asset_currencies = ASSET_VALUE_CURRENCIES

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)

    @staticmethod
    def _prep_markets(marketscfg, markets, tickers):
        """Prepare markets data."""

        tickers_dict = {}

        for market in marketscfg:
            if market not in tickers_dict:
                tickers_dict[market] = {}
                ticker_details = next(
                    item for item in tickers if item["symbol"] == market
                )
                market_details = next(
                    item for item in markets if item["symbol"] == market
                )
                combined_details_dict = {
                    **ticker_details,
                    **market_details,
                }
                tickers_dict[market].update(combined_details_dict)

        return tickers_dict

    @staticmethod
    def _prep_tickers(asset_currencies, tickers):
        """Prepare tickers data."""

        asset_tickers_dict = {}

        for asset in asset_currencies:
            # Skip the ASSET_VALUE_BASE as we calculate it differently
            if asset != ASSET_VALUE_BASE:
                currency = f"{asset}{ASSET_VALUE_BASE}"

                if currency not in asset_tickers_dict:
                    asset_tickers_dict[currency] = {}
                    ticker_details = next(
                        item for item in tickers if item["symbol"] == currency
                    )
                    asset_tickers_dict[currency].update(ticker_details)

        return asset_tickers_dict

    @staticmethod
    def _prep_balances(balances, tickers):
        """Prepare balances data."""

        balances_dict = {}

        for balance in balances:
            if balance["asset"] not in balances_dict:
                balances_dict[balance["asset"]] = {}
                balances_dict[balance["asset"]].update(balance)
                base_asset_ticker_details = None

                total_balance = float(balance["free"]) + float(balance["locked"])

                if ASSET_VALUE_BASE not in balance["asset"]:
                    # Prevent that we try to search ASSET_VALUE_BASE+ASSET_VALUE_BASE (e.g. BTCBTC)
                    base_asset_symbol = str(balance["asset"] + ASSET_VALUE_BASE)
                    try:
                        base_asset_ticker_details = next(
                            item
                            for item in tickers
                            if item["symbol"] == base_asset_symbol
                        )
                    except StopIteration:
                        continue
                else:
                    balances_dict[balance["asset"]][
                        "asset_value_in_base_asset"
                    ] = total_balance

                if base_asset_ticker_details:
                    # If we can find a pair with ASSET_VALUE_BASE, include it in the dict
                    balances_dict[balance["asset"]][ASSET_VALUE_BASE] = {}
                    balances_dict[balance["asset"]][ASSET_VALUE_BASE].update(
                        base_asset_ticker_details
                    )
                    balances_dict[balance["asset"]][
                        "asset_value_in_base_asset"
                    ] = total_balance * float(base_asset_ticker_details["lastPrice"])

        return balances_dict

    async def _async_update_data(self):
        """Fetch Binance data."""
        try:
            binance = await AsyncClient.create(
                api_key=self._api_key, api_secret=self._api_secret
            )

            tickers = await binance.get_ticker()
            markets = (await binance.get_exchange_info())["symbols"]
            balances = (await binance.get_account())["balances"]
            open_orders = await binance.get_open_orders()

            result_dict = {
                "tickers": self._prep_markets(self.markets, tickers, markets)
            }
            result_dict["asset_tickers"] = self._prep_tickers(
                self.asset_currencies, tickers
            )
            result_dict["balances"] = self._prep_balances(balances, tickers)

            if open_orders:
                result_dict["open_orders"] = open_orders
            else:
                result_dict["open_orders"] = []

            return result_dict

        except BinanceAPIException as error:
            _LOGGER.error("Binance API error: %s", error)
            raise ConfigEntryNotReady from error
        except BinanceRequestException as error:
            _LOGGER.error("Binance API Request error: %s", error)
            return None
        finally:
            await binance.close_connection()
