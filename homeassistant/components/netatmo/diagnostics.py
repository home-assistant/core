"""Diagnostics support for Netatmo."""
from __future__ import annotations

from homeassistant.components.diagnostics import REDACTED
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DATA_HANDLER, DOMAIN
from .data_handler import NetatmoDataHandler


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict:
    """Return diagnostics for a config entry."""
    data_handler: NetatmoDataHandler = hass.data[DOMAIN][config_entry.entry_id][
        DATA_HANDLER
    ]

    diagnostics_data = {
        "info": {
            **config_entry.as_dict(),
            "webhook_registered": data_handler.webhook,
        },
        "data": data_handler.data,
    }

    if "token" in diagnostics_data["info"]["data"]:
        diagnostics_data["info"]["data"]["token"]["access_token"] = REDACTED
        diagnostics_data["info"]["data"]["token"]["refresh_token"] = REDACTED
        diagnostics_data["info"]["data"]["token"]["restricted_access_token"] = REDACTED
        diagnostics_data["info"]["data"]["token"]["restricted_refresh_token"] = REDACTED

    if "webhook_id" in diagnostics_data["info"]["data"]:
        diagnostics_data["info"]["data"]["webhook_id"] = REDACTED

    if "weather_areas" in diagnostics_data["info"].get("options", {}):
        for area in diagnostics_data["info"]["options"]["weather_areas"]:
            for attr in ("lat_ne", "lat_sw", "lon_ne", "lon_sw"):
                diagnostics_data["info"]["options"]["weather_areas"][area][
                    attr
                ] = REDACTED

    return diagnostics_data
