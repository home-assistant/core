"""Diagnostics support for P1 Monitor."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import HWEnergyDeviceUpdateCoordinator

TO_REDACT = {CONF_IP_ADDRESS, "serial", "wifi_ssid"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: HWEnergyDeviceUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    meter_data = {
        "device": asdict(coordinator.data["device"]),
        "data": asdict(coordinator.data["data"]),
        "state": asdict(coordinator.data["state"])
        if coordinator.data["state"] is not None
        else None,
        "system": asdict(coordinator.data["system"])
        if coordinator.data["system"] is not None
        else None,
    }

    return {
        "entry": async_redact_data(entry.data, TO_REDACT),
        "data": async_redact_data(meter_data, TO_REDACT),
    }
