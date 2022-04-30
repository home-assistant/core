"""Diagnostics support for Coinbase."""

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_API_TOKEN, CONF_ID
from homeassistant.core import HomeAssistant

from . import CoinbaseData
from .const import API_ACCOUNT_AMOUNT, API_RESOURCE_PATH, CONF_TITLE, DOMAIN

TO_REDACT = {
    API_ACCOUNT_AMOUNT,
    API_RESOURCE_PATH,
    CONF_API_KEY,
    CONF_API_TOKEN,
    CONF_ID,
    CONF_TITLE,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict:
    """Return diagnostics for a config entry."""
    instance: CoinbaseData = hass.data[DOMAIN][entry.entry_id]

    return async_redact_data(
        {
            "entry": entry.as_dict(),
            "accounts": instance.accounts,
        },
        TO_REDACT,
    )
