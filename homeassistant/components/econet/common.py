"""Common code for econet component."""

import logging

from pyeconet.api import EcoNetApiInterface

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__package__)


async def async_get_api_from_data(data: dict) -> EcoNetApiInterface:
    """Get a new API from data."""
    return await EcoNetApiInterface.login(
        email=data[CONF_EMAIL], password=data[CONF_PASSWORD]
    )


def set_data_api(
    hass: HomeAssistant, config_entry: ConfigEntry, api: EcoNetApiInterface
) -> None:
    """Set API into hass data."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(config_entry.entry_id, {})
    hass.data[DOMAIN][config_entry.entry_id] = api


def get_data_api(hass: HomeAssistant, config_entry: ConfigEntry) -> EcoNetApiInterface:
    """Get API from hass data."""
    return hass.data[DOMAIN][config_entry.entry_id]
