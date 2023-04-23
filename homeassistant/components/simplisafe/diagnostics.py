"""Diagnostics support for SimpliSafe."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_CODE,
    CONF_LOCATION,
    CONF_TOKEN,
    CONF_UNIQUE_ID,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant

from . import SimpliSafe
from .const import DOMAIN

CONF_CREDIT_CARD = "creditCard"
CONF_EXPIRES = "expires"
CONF_LOCATION_NAME = "locationName"
CONF_PAYMENT_PROFILE_ID = "paymentProfileId"
CONF_SERIAL = "serial"
CONF_SID = "sid"
CONF_SYSTEM_ID = "system_id"
CONF_TITLE = "title"
CONF_UID = "uid"
CONF_WIFI_SSID = "wifi_ssid"

TO_REDACT = {
    CONF_ADDRESS,
    CONF_CODE,
    CONF_CREDIT_CARD,
    CONF_EXPIRES,
    CONF_LOCATION,
    CONF_LOCATION_NAME,
    CONF_PAYMENT_PROFILE_ID,
    CONF_SERIAL,
    CONF_SID,
    CONF_SYSTEM_ID,
    # Config entry title may contain sensitive data:
    CONF_TITLE,
    CONF_TOKEN,
    CONF_UID,
    # Config entry unique ID may contain sensitive data:
    CONF_UNIQUE_ID,
    CONF_USERNAME,
    CONF_WIFI_SSID,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    simplisafe: SimpliSafe = hass.data[DOMAIN][entry.entry_id]

    return async_redact_data(
        {
            "entry": entry.as_dict(),
            "subscription_data": simplisafe.subscription_data,
            "systems": [system.as_dict() for system in simplisafe.systems.values()],
        },
        TO_REDACT,
    )
