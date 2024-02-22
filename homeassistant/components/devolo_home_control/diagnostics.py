"""Diagnostics support for devolo Home Control."""
from __future__ import annotations

from typing import Any

from devolo_home_control_api.homecontrol import HomeControl

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import DOMAIN

TO_REDACT = {CONF_PASSWORD, CONF_USERNAME}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    gateways: list[HomeControl] = hass.data[DOMAIN][entry.entry_id]["gateways"]

    device_info = []
    for gateway in gateways:
        device_info.append(
            {
                "gateway": {
                    "local_connection": gateway.gateway.local_connection,
                    "firmware_version": gateway.gateway.firmware_version,
                },
                "devices": [
                    {
                        "device_id": device_id,
                        "device_model_uid": properties.device_model_uid,
                        "device_type": properties.device_type,
                        "name": properties.name,
                    }
                    for device_id, properties in gateway.devices.items()
                ],
            }
        )

    diag_data = {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "device_info": device_info,
    }

    return diag_data
