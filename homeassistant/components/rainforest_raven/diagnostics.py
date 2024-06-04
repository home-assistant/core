"""Diagnostics support for a Rainforest RAVEn device."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MAC
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN
from .coordinator import RAVEnDataCoordinator

TO_REDACT_CONFIG = {CONF_MAC}
TO_REDACT_DATA = {"device_mac_id", "meter_mac_id"}


@callback
def async_redact_meter_macs(data: dict) -> dict:
    """Redact meter MAC addresses from mapping keys."""
    if not data.get("Meters"):
        return data

    redacted = {**data, "Meters": {}}
    for idx, mac_id in enumerate(data["Meters"]):
        redacted["Meters"][f"**REDACTED{idx}**"] = data["Meters"][mac_id]

    return redacted


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> Mapping[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: RAVEnDataCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    return {
        "config_entry": async_redact_data(config_entry.as_dict(), TO_REDACT_CONFIG),
        "data": async_redact_meter_macs(
            async_redact_data(coordinator.data, TO_REDACT_DATA)
        ),
    }
