"""Diagnostics support for Tibber."""
from __future__ import annotations

from typing import Any

import tibber

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


from .const import DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    # If the ConfigEntry is not ready there is no DOMAIN data available,
    # it can occur either if it has never been started
    # or connection to the Tibber API failed
    tibber_connection: tibber.Tibber | None = hass.data.get(DOMAIN)

    homes: dict[str, Any] = {}
    if tibber_connection:
        for home in tibber_connection.get_homes(only_active=False):
            homes[home.home_id] = {
                "last_data_timestamp": home.last_data_timestamp,
                "has_active_subscription": home.has_active_subscription,
                "has_real_time_consumption": home.has_real_time_consumption,
                "last_cons_data_timestamp": home.last_cons_data_timestamp,
                "country": home.country,
            }

    # indicate in the diag data if the Tibber connection was established
    return {"tibber_connection": bool(tibber_connection), "homes": homes}
