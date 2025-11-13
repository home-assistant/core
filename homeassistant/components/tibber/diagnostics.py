"""Diagnostics support for Tibber."""

from __future__ import annotations

from typing import Any

import tibber

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import API_TYPE_DATA_API, API_TYPE_GRAPHQL, CONF_API_TYPE, DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    api_type = config_entry.data.get(CONF_API_TYPE, API_TYPE_GRAPHQL)
    domain_data = hass.data.get(DOMAIN, {})

    if api_type == API_TYPE_GRAPHQL:
        runtime = domain_data.get(API_TYPE_GRAPHQL, {}).get(config_entry.entry_id)
        if runtime and hasattr(runtime, "tibber"):
            tibber_connection: tibber.Tibber = runtime.tibber
            return {
                "api_type": API_TYPE_GRAPHQL,
                "homes": [
                    {
                        "last_data_timestamp": home.last_data_timestamp,
                        "has_active_subscription": home.has_active_subscription,
                        "has_real_time_consumption": home.has_real_time_consumption,
                        "last_cons_data_timestamp": home.last_cons_data_timestamp,
                        "country": home.country,
                    }
                    for home in tibber_connection.get_homes(only_active=False)
                ],
            }
        return {
            "api_type": API_TYPE_GRAPHQL,
            "homes": [],
        }

    return {
        "api_type": API_TYPE_DATA_API,
    }
