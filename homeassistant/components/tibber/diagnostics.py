"""Diagnostics support for Tibber."""
from __future__ import annotations

import tibber

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant

from .const import DOMAIN

REDACTED = "REDACTED"


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict:
    """Return diagnostics for a config entry."""
    tibber_connection: tibber.Tibber = hass.data[DOMAIN]

    diagnostics_data = {
        "info": {
            **config_entry.as_dict(),
        },
    }

    homes = {}
    for home in tibber_connection.get_homes(only_active=False):
        homes[home.home_id] = {
            "last_data_timestamp": home.last_data_timestamp,
            "has_active_subscription": home.has_active_subscription,
            "has_real_time_consumption": home.has_real_time_consumption,
            "last_cons_data_timestamp": home.last_cons_data_timestamp,
            "country": home.country,
        }
    diagnostics_data["homes"] = homes
    diagnostics_data["info"]["data"][CONF_ACCESS_TOKEN] = REDACTED

    return diagnostics_data
