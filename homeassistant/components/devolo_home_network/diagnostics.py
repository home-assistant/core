"""Diagnostics support for devolo Home Network."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant

from . import DevoloHomeNetworkConfigEntry

TO_REDACT = {CONF_PASSWORD}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: DevoloHomeNetworkConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    device = entry.runtime_data.device

    diag_data = {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "device_info": {
            "mt_number": device.mt_number,
            "product": device.product,
            "firmware": device.firmware_version,
            "device_api": device.device is not None,
            "plcnet_api": device.plcnet is not None,
        },
    }

    if device.device:
        diag_data["device_info"]["features"] = device.device.features

    return diag_data
