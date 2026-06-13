"""Diagnostics support for Netatmo."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .data_handler import ACCOUNT, NetatmoConfigEntry

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
    hass: HomeAssistant, config_entry: NetatmoConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data_handler = config_entry.runtime_data

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
                data_handler.account.raw_data,
                TO_REDACT,
            )
        },
    }
