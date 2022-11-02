"""Diagnostics support for Velbus."""
from __future__ import annotations

from typing import Any

from huawei_solar import HuaweiSolarBridge

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant

from . import HuaweiSolarUpdateCoordinator
from .const import DATA_UPDATE_COORDINATORS, DOMAIN

TO_REDACT = {CONF_PASSWORD}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    coordinators: list[HuaweiSolarUpdateCoordinator] = hass.data[DOMAIN][
        entry.entry_id
    ][DATA_UPDATE_COORDINATORS]

    diagnostics_data = {
        "config_entry_data": async_redact_data(dict(entry.data), TO_REDACT)
    }
    for coordinator in coordinators:
        diagnostics_data[
            f"slave_{coordinator.bridge.slave_id}"
        ] = await _build_bridge_diagnostics_info(coordinator.bridge)

        diagnostics_data[f"slave_{coordinator.bridge.slave_id}_data"] = coordinator.data

    return diagnostics_data


async def _build_bridge_diagnostics_info(bridge: HuaweiSolarBridge) -> dict[str, Any]:

    diagnostics_data = {
        "model_name": bridge.model_name,
        "pv_string_count": bridge.pv_string_count,
        "has_optimizers": bridge.has_optimizers,
        "battery_1_type": bridge.battery_1_type,
        "battery_2_type": bridge.battery_2_type,
        "power_meter_type": bridge.power_meter_type,
    }

    return diagnostics_data
