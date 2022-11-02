"""Diagnostics support for Netatmo."""
from __future__ import annotations

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DATA_HANDLER, DOMAIN
from .data_handler import ACCOUNT, NetatmoDataHandler

TO_REDACT = {
    "access_token",
    "refresh_token",
    "restricted_access_token",
    "restricted_refresh_token",
    "webhook_id",
    "cloudhook_url",
    "lat_ne",
    "lat_sw",
    "lon_ne",
    "lon_sw",
    "coordinates",
    "name",
    "timetable",
    "zones",
    "pseudo",
    "url",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict:
    """Return diagnostics for a config entry."""
    data_handler: NetatmoDataHandler = hass.data[DOMAIN][config_entry.entry_id][
        DATA_HANDLER
    ]

    return {
        "info": async_redact_data(
            {
                **config_entry.as_dict(),
                "webhook_registered": data_handler.webhook,
            },
            TO_REDACT,
        ),
        "data": {
            ACCOUNT: async_redact_data(
                getattr(data_handler.account, "raw_data"),
                TO_REDACT,
            )
        },
    }
