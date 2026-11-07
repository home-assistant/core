"""Diagnostics support for Fressnapf Tracker."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_EMAIL
from homeassistant.core import HomeAssistant

from .const import CONF_CUSTOMER_ID, CONF_PHONE_NUMBER, CONF_USER_ID
from .coordinator import FressnapfTrackerConfigEntry

TO_REDACT = {
    CONF_ACCESS_TOKEN,
    CONF_CUSTOMER_ID,
    CONF_EMAIL,
    CONF_PHONE_NUMBER,
    CONF_USER_ID,
    "additional_parameters",
    "icon",
    "inside_geofence",
    "last_position",
    "lat",
    "lng",
    "name",
    "serialnumber",
    "token",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: FressnapfTrackerConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return async_redact_data(
        {
            "entry_data": dict(entry.data),
            "trackers": [
                {
                    "device": coordinator.device.model_dump(mode="json"),
                    "data": coordinator.data.model_dump(mode="json"),
                }
                for coordinator in entry.runtime_data
            ],
        },
        TO_REDACT,
    )
