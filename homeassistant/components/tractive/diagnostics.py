"""Diagnostics support for Tractive."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import (
    ATTR_DEVICE_ID,
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_UNIQUE_ID,
)
from homeassistant.core import HomeAssistant

from .coordinator import TractiveConfigEntry

TO_REDACT = {
    ATTR_DEVICE_ID,
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_UNIQUE_ID,
    "_id",
    "birthday",
    "chip_id",
    "home_location",
    "instagram_username",
    "name",
    "title",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: TractiveConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    trackables = config_entry.runtime_data.trackables

    return async_redact_data(
        {
            "config_entry": config_entry.as_dict(),
            "trackables": [item.pet_details for item in trackables],
        },
        TO_REDACT,
    )
