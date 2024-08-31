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

TO_REDACT = {
    CONF_IP_ADDRESS,
    "serial",
    "wifi_ssid",
    "unique_meter_id",
    "unique_id",
    "gas_unique_id",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: HWEnergyDeviceUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    state: dict[str, Any] | None = None
    if coordinator.data.state:
        state = asdict(coordinator.data.state)

    system: dict[str, Any] | None = None
    if coordinator.data.system:
        system = asdict(coordinator.data.system)

    return async_redact_data(
        {
            "entry": async_redact_data(entry.data, TO_REDACT),
            "data": {
                "device": asdict(coordinator.data.device),
                "data": asdict(coordinator.data.data),
                "state": state,
                "system": system,
            },
        },
        TO_REDACT,
    )
