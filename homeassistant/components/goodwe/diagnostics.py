"""Diagnostics support for Goodwe."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import GoodweConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: GoodweConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    inverter = config_entry.runtime_data.inverter

    return {
        "config_entry": config_entry.as_dict(),
        "inverter": {
            "model_name": inverter.model_name,
            "rated_power": inverter.rated_power,
            "firmware": inverter.firmware,
            "arm_firmware": inverter.arm_firmware,
            "dsp1_version": inverter.dsp1_version,
            "dsp2_version": inverter.dsp2_version,
            "dsp_svn_version": inverter.dsp_svn_version,
            "arm_version": inverter.arm_version,
            "arm_svn_version": inverter.arm_svn_version,
        },
    }
