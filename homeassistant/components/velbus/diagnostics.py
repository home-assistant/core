"""Diagnostics support for Velbus."""
from __future__ import annotations

from typing import Any

from velbusaio.module import Module as VelbusModule

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from .const import DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    cntrl = hass.data[DOMAIN][entry.entry_id]["cntrl"]
    diag: dict[str, Any] = {"entry": entry.as_dict(), "modules": []}
    for mod in cntrl.get_modules().values():
        diag["modules"].append(build_module_diag_info(mod))
    return diag


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device entry."""
    cntrl = hass.data[DOMAIN][entry.entry_id]["cntrl"]
    chan = list(next(iter(device.identifiers)))[1]
    mods = cntrl.get_modules()
    return build_module_diag_info(mods[int(chan)])


def build_module_diag_info(mod: VelbusModule) -> dict[str, Any]:
    """Build per module diag info."""
    diag: dict[str, Any] = {
        "type": mod.get_type_name(),
        "address": mod.get_addresses(),
        "name": mod.get_name(),
        "sw_version": mod.get_sw_version(),
        "is_loaded": mod.is_loaded(),
        "channels": build_channels_diag_info(mod.get_channels()),
    }
    return diag


def build_channels_diag_info(chans: dict[str, Any]) -> dict[str, Any]:
    """Build diag info for all channels."""
    diag: dict[str, Any] = {}
    for chan in chans.values():
        diag[chan.get_channel_number()] = {}
        for key, value in chan.__dict__.items():
            if key not in ["_module", "_writer", "_name_parts", "_on_status_update"]:
                diag[chan.get_channel_number()][key.replace("_", "", 1)] = value
    return diag
