"""Diagnostics support for Whirlpool."""

from __future__ import annotations

from typing import Any

from whirlpool.appliance import Appliance

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import WhirlpoolConfigEntry

TO_REDACT = {
    "SERIAL_NUMBER",
    "macaddress",
    "username",
    "password",
    "token",
    "unique_id",
    "SAID",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    config_entry: WhirlpoolConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    def get_appliance_diagnostics(appliance: Appliance) -> dict[str, Any]:
        return {
            "data_model": appliance.appliance_info.data_model,
            "category": appliance.appliance_info.category,
            "model_number": appliance.appliance_info.model_number,
        }

    appliances_manager = config_entry.runtime_data
    diagnostics_data = {
        "washer_dryers": {
            wd.name: get_appliance_diagnostics(wd)
            for wd in appliances_manager.washer_dryers
        },
        "aircons": {
            ac.name: get_appliance_diagnostics(ac) for ac in appliances_manager.aircons
        },
        "ovens": {
            oven.name: get_appliance_diagnostics(oven)
            for oven in appliances_manager.ovens
        },
    }

    return {
        "config_entry": async_redact_data(config_entry.as_dict(), TO_REDACT),
        "appliances": async_redact_data(diagnostics_data, TO_REDACT),
    }
