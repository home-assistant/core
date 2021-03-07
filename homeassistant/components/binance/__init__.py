"""Gather the market details from Binance."""
import logging
from typing import Dict, List, Optional

from binance import AsyncClient
from binance.exceptions import BinanceAPIException, BinanceRequestException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    ASSET_VALUE_CURRENCIES,
    CONF_API_SECRET,
    CONF_MARKETS,
    DOMAIN,
    SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: Dict) -> bool:
    """Set up the component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Binance from a config entry."""
    api_key = entry.data[CONF_API_KEY]
    api_secret = entry.data[CONF_API_SECRET]
    symbols = entry.data[CONF_MARKETS]

    coordinator = BinanceDataUpdateCoordinator(hass, api_key, api_secret, symbols)
    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )

    return True


class BinanceDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to get the latest data from Binance."""

    def __init__(
        self, hass, api_key, api_secret, symbols, balances: Optional[List] = None
    ):
        """Initialize the data object."""
        self._api_key = api_key
        self._api_secret = api_secret

        self.symbols = symbols
        self.asset_currencies = ASSET_VALUE_CURRENCIES

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)

    async def _async_update_data(self):
        """Fetch Binance data."""
        try:
            binance = await AsyncClient.create(
                api_key=self._api_key, api_secret=self._api_secret
            )

            all_tickers = await binance.get_ticker()
            all_markets = await binance.get_exchange_info()
            all_balances = await binance.get_account()

            tickers_dict = {}

            for sym in self.symbols:
                if sym not in tickers_dict:
                    tickers_dict[sym] = {}
                    ticker_details = next(
                        item for item in all_tickers if item["symbol"] == sym
                    )
                    market_details = next(
                        item for item in all_markets["symbols"] if item["symbol"] == sym
                    )
                    combined_details_dict = {**ticker_details, **market_details}
                    tickers_dict[sym].update(combined_details_dict)

            result_dict = {"tickers": tickers_dict}

            asset_tickers_dict = {}

            for sym in self.asset_currencies:
                if sym == "USDT":
                    # Skip the loop as we calculate USDT differently
                    break

                currency = sym.upper() + "USDT"

                if currency not in asset_tickers_dict:
                    asset_tickers_dict[currency] = {}
                    ticker_details = next(
                        item for item in all_tickers if item["symbol"] == currency
                    )
                    asset_tickers_dict[currency].update(ticker_details)

            result_dict["asset_tickers"] = asset_tickers_dict

            balances_dict = {}

            for balance in all_balances["balances"]:
                if (
                    balance["free"] > "0.00000000"
                    and balance["asset"] not in balances_dict
                ):
                    balances_dict[balance["asset"]] = {}
                    balances_dict[balance["asset"]].update(balance)

                    if "USDT" not in balance["asset"]:
                        # Prevent that we try to search USDTUSDT
                        usdt_symbol = str(balance["asset"] + "USDT")
                        usdt_ticker_details = next(
                            item
                            for item in all_tickers
                            if item["symbol"] == usdt_symbol
                        )
                    else:
                        balances_dict[balance["asset"]]["asset_value_in_usdt"] = float(
                            balance["free"]
                        ) + float(balance["locked"])

                    if usdt_ticker_details:
                        # If we can find a USDT pair, include it in the dict
                        balances_dict[balance["asset"]]["USDT"] = {}
                        balances_dict[balance["asset"]]["USDT"].update(
                            usdt_ticker_details
                        )
                        balances_dict[balance["asset"]]["asset_value_in_usdt"] = (
                            float(balance["free"]) + float(balance["locked"])
                        ) * float(usdt_ticker_details["lastPrice"])

            result_dict["balances"] = balances_dict

            open_orders = await binance.get_open_orders()
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
