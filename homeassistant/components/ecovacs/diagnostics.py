"""Ecovacs diagnostics."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import CONF_OVERRIDE_MQTT_URL, CONF_OVERRIDE_REST_URL, DOMAIN
from .controller import EcovacsController

REDACT_CONFIG = {
    CONF_USERNAME,
    CONF_PASSWORD,
    "title",
    CONF_OVERRIDE_MQTT_URL,
    CONF_OVERRIDE_REST_URL,
}
REDACT_DEVICE = {"did", CONF_NAME, "homeId"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    controller: EcovacsController = hass.data[DOMAIN][config_entry.entry_id]
    diag: dict[str, Any] = {
        "config": async_redact_data(config_entry.as_dict(), REDACT_CONFIG)
    }

    diag["devices"] = [
        async_redact_data(device.device_info.api_device_info, REDACT_DEVICE)
        for device in controller.devices
    ]
    diag["legacy_devices"] = [
        async_redact_data(device.vacuum, REDACT_DEVICE)
        for device in controller.legacy_devices
    ]

    return diag
