"""Gather the market details from Bittrex."""
import logging
from typing import Dict, List, Optional

from aiobittrexapi import Bittrex
from aiobittrexapi.errors import (
    BittrexApiError,
    BittrexInvalidAuthentication,
    BittrexResponseError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_API_SECRET, CONF_BALANCES, CONF_MARKETS, DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: Dict) -> bool:
    """Set up the component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Bittrex from a config entry."""
    api_key = entry.data[CONF_API_KEY]
    api_secret = entry.data[CONF_API_SECRET]
    symbols = entry.data[CONF_MARKETS]

    if CONF_BALANCES in entry.data:
        balances = entry.data[CONF_BALANCES]
        coordinator = BittrexDataUpdateCoordinator(
            hass, api_key, api_secret, symbols, balances
        )
    else:
        coordinator = BittrexDataUpdateCoordinator(hass, api_key, api_secret, symbols)

    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )

    return True


class BittrexDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to get the latest data from Bittrex."""

    def __init__(
        self, hass, api_key, api_secret, symbols, balances: Optional[List] = None
    ):
        """Initialize the data object."""
        self.bittrex = Bittrex(api_key, api_secret)
        self.symbols = symbols
        self.balances = balances or None

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)

    async def _async_update_data(self):
        """Fetch Bittrex data."""
        try:
            tickers = await self.bittrex.get_tickers(symbol=self.symbols)
            result_dict = {"tickers": tickers}

            if self.balances:
                balances = await self.bittrex.get_balances(symbol=self.balances)
                result_dict["balances"] = balances

            open_orders = await self.bittrex.get_open_orders()
            if open_orders:
                result_dict["open_orders"] = open_orders

            closed_orders = await self.bittrex.get_closed_orders()
            if closed_orders:
                result_dict["closed_orders"] = closed_orders

            return result_dict
        except BittrexInvalidAuthentication as error:
            _LOGGER.error("Bittrex authentication error: %s", error)
            raise ConfigEntryNotReady from error
        except BittrexApiError as error:
            _LOGGER.error("Bittrex API error: %s", error)
            raise ConfigEntryNotReady from error
        except BittrexResponseError as error:
            _LOGGER.error("Bittrex sensor error: %s", error)
            return None
