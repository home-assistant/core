"""Diagnostics support for Xiaomi Miio."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_DEVICE, CONF_MAC, CONF_TOKEN, CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant

from .const import (
    CONF_CLOUD_PASSWORD,
    CONF_CLOUD_USERNAME,
    CONF_FLOW_TYPE,
    CONF_WIFI_REPEATER,
)
from .typing import XiaomiMiioConfigEntry

TO_REDACT = {
    CONF_CLOUD_PASSWORD,
    CONF_CLOUD_USERNAME,
    CONF_MAC,
    CONF_TOKEN,
    CONF_UNIQUE_ID,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: XiaomiMiioConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    diagnostics_data: dict[str, Any] = {
        "config_entry": async_redact_data(config_entry.as_dict(), TO_REDACT)
    }

    if config_entry.data[CONF_FLOW_TYPE] == CONF_WIFI_REPEATER:
        # WifiRepeaterStatus wraps the raw station list in .data.
        if (data := config_entry.runtime_data.device_coordinator.data) is not None:
            diagnostics_data["coordinator_data"] = async_redact_data(
                data.data, TO_REDACT | {"ip"}
            )
    elif config_entry.data[CONF_FLOW_TYPE] == CONF_DEVICE:
        coordinator = config_entry.runtime_data.device_coordinator
        if isinstance(coordinator.data, dict):
            diagnostics_data["coordinator_data"] = coordinator.data
        else:
            diagnostics_data["coordinator_data"] = repr(coordinator.data)
    return diagnostics_data
