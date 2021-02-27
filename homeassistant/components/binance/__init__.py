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

from .const import CONF_API_SECRET, CONF_MARKETS, DOMAIN, SCAN_INTERVAL

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

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)

    async def _async_update_data(self):
        """Fetch Binance data."""
        try:
            binance = await AsyncClient.create(
                api_key=self._api_key, api_secret=self._api_secret
            )

            all_tickers = await binance.get_ticker()
            tickers_dict = {}

            for sym in self.symbols:
                if sym not in tickers_dict:
                    tickers_dict[sym] = {}
                    details = next(
                        item for item in all_tickers if item["symbol"] == sym
                    )
                    tickers_dict[sym].update(details)

            result_dict = {"tickers": tickers_dict}

            all_balances = await binance.get_account()
            balances_dict = {}

            for balance in all_balances["balances"]:
                if balance["free"] != "0.00000000":
                    balances_dict[balance["asset"]] = {}
                    balances_dict[balance["asset"]].update(balance)

            result_dict["balances"] = balances_dict

            open_orders = await binance.get_open_orders()
            if open_orders:
                result_dict["open_orders"] = open_orders

            return result_dict
        except BinanceAPIException as error:
            _LOGGER.error("Binance API error: %s", error)
            raise ConfigEntryNotReady from error
        except BinanceRequestException as error:
            _LOGGER.error("Binance API Request error: %s", error)
            return None
        finally:
            await binance.close_connection()
