"""Gather the market details from Bittrex."""
import logging
from typing import Dict

from aiobittrexapi import Bittrex
from aiobittrexapi.errors import (
    BittrexApiError,
    BittrexInvalidAuthentication,
    BittrexResponseError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_API_SECRET, CONF_MARKETS, DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.deprecated(CONF_API_KEY),
            cv.deprecated(CONF_API_SECRET),
            cv.deprecated(CONF_MARKETS),
            vol.Schema(
                {
                    vol.Optional(CONF_API_KEY): cv.string,
                    vol.Optional(CONF_API_SECRET): cv.string,
                    vol.Optional(CONF_MARKETS): cv.string,
                }
            ),
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: Dict) -> bool:
    """Set up the component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Bittrex from a config entry."""
    api_key = entry.data[CONF_API_KEY]
    api_secret = entry.data[CONF_API_SECRET]
    symbols = entry.data[CONF_MARKETS]

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

    def __init__(self, hass, api_key, api_secret, symbols):
        """Initialize the data object."""
        self.bittrex = Bittrex(api_key, api_secret)
        self.symbols = symbols
        self.hass = hass

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)

    async def _async_update_data(self):
        """Fetch Bittrex data."""
        try:
            return await self.bittrex.get_tickers(symbol=self.symbols)
        except BittrexInvalidAuthentication as error:
            _LOGGER.error("Bittrex authentication error: %s", error)
            raise ConfigEntryNotReady from error
        except BittrexApiError as error:
            _LOGGER.error("Bittrex API error: %s", error)
            raise ConfigEntryNotReady from error
        except BittrexResponseError as error:
            _LOGGER.error("Bittrex sensor error: %s", error)
            return None
