"""Diagnostics support for Coinbase."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_API_TOKEN, CONF_ID
from homeassistant.core import HomeAssistant

from . import CoinbaseData
from .const import API_ACCOUNT_AMOUNT, API_RESOURCE_PATH, DOMAIN

TO_REDACT = {
    API_ACCOUNT_AMOUNT,
    API_RESOURCE_PATH,
    CONF_API_KEY,
    CONF_API_TOKEN,
    CONF_ID,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict:
    """Return diagnostics for a config entry."""
    instance: CoinbaseData = hass.data[DOMAIN][entry.entry_id]

    diag_data: dict[str, Any] = {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "data": [],
    }
    if not isinstance(instance.accounts, list):
        return diag_data

    diag_data["data"] = [
        async_redact_data(account, TO_REDACT) for account in instance.accounts
    ]
    return diag_data
