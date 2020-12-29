"""Gather the market details from Bittrex."""
from datetime import timedelta
import logging
from typing import Dict

from async_timeout import timeout
from bittrex_api.bittrex import BittrexV3
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_API_SECRET, CONF_MARKETS, DOMAIN

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
    hass.data.setdefault(DOMAIN, {})

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Bittrex from a config entry."""
    api_key = entry.data[CONF_API_KEY]
    api_secret = entry.data[CONF_API_SECRET]
    markets = entry.data[CONF_MARKETS]

    websession = async_get_clientsession(hass)

    coordinator = BittrexDataUpdateCoordinator(
        hass, websession, api_key, api_secret, markets
    )
    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN] = coordinator

    if entry.unique_id is None:
        hass.config_entries.async_update_entry(entry, unique_id=f"{coordinator.name}")

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )

    return True


class BittrexDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to get the latest data from Bittrex."""

    def __init__(self, hass, session, api_key, api_secret, markets):
        """Initialize the data object."""
        self.bittrex = BittrexV3(api_key, api_secret, reverse_market_names=False)
        self.markets = markets
        self._authenticate()

        update_interval = timedelta(seconds=30)

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=update_interval)

    def _authenticate(self):
        """Test authentication to Bittrex."""
        try:
            bittrex_account = self.bittrex.get_account()["accountId"]

            if not bittrex_account:
                raise Exception("Authentication failed")
        except Exception as error:
            raise ConfigEntryNotReady from error

    async def _async_update_data(self):
        """Fetch Bittrex data."""
        try:
            async with timeout(10):
                tickers = self.bittrex.get_tickers()

                data = []

                for market in self.markets:
                    data.append(
                        next(item for item in tickers if item["symbol"] == market)
                    )

        except Exception as err:
            _LOGGER.error("Bittrex sensor error: %s", err)
            return None

        return data
