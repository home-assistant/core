"""Gather the market details from Bittrex."""
import logging
from typing import Dict

from bittrex_api.bittrex import BittrexV3
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

    if entry.unique_id is None:
        hass.config_entries.async_update_entry(entry, unique_id=f"{coordinator.name}")

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )

    return True


class BittrexDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to get the latest data from Bittrex."""

    def __init__(self, hass, api_key, api_secret, symbols):
        """Initialize the data object."""
        self.bittrex = BittrexV3(api_key, api_secret, reverse_market_names=False)
        self.symbols = symbols
        self._authenticate()

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)

    def _authenticate(self):
        """Test authentication to Bittrex."""
        try:
            bittrex_account = self.bittrex.get_account()["accountId"]

            if not bittrex_account:
                raise Exception("Authentication failed")
        except Exception as error:
            raise ConfigEntryNotReady from error

    async def _get_tickers(self):
        """Get the latest tickers."""
        try:
            result = self.bittrex.get_tickers()
            return result
        except Exception as error:
            _LOGGER.error("Bittrex get_tickers error: %s", error)
            return None

    async def _async_update_data(self):
        """Fetch Bittrex data."""
        try:
            tickers = await self._get_tickers()
            data = []

            for symbol in self.symbols:
                data.append(next(item for item in tickers if item["symbol"] == symbol))
            return data

        except Exception as error:
            _LOGGER.error("Bittrex sensor error: %s", error)
            return None
