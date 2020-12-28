"""Gather the market details from Bittrex."""
import logging
from typing import Dict

from bittrex_api.bittrex import Bittrex
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv

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

    if len(hass.config_entries.async_entries(DOMAIN)) > 0:
        return True

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Bittrex from a config entry."""
    try:
        bittrex = Bittrex(
            entry.data[CONF_API_KEY], entry.data[CONF_API_SECRET], debug_level=3
        )
        bittrex_account = bittrex.v3.get_account()["accountId"]

        if not bittrex_account:
            raise Exception("Authentication failed")
    except Exception as error:
        raise ConfigEntryNotReady from error

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Bittrex config entry."""
    hass.data[DOMAIN].pop(entry.entry_id)

    return True
