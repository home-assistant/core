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
    controller = hass.data[DOMAIN][entry.entry_id]["cntrl"]
    data: dict[str, Any] = {"entry": entry.as_dict(), "modules": []}
    for module in controller.get_modules().values():
        data["modules"].append(build_module_diagnostics_info(module))
    return data


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device entry."""
    controller = hass.data[DOMAIN][entry.entry_id]["cntrl"]
    chan = list(next(iter(device.identifiers)))[1]
    modules = controller.get_modules()
    return build_module_diagnostics_info(modules[int(chan)])


def build_module_diagnostics_info(module: VelbusModule) -> dict[str, Any]:
    """Build per module diagnostics info."""
    data: dict[str, Any] = {
        "type": module.get_type_name(),
        "address": module.get_addresses(),
        "name": module.get_name(),
        "sw_version": module.get_sw_version(),
        "is_loaded": module.is_loaded(),
        "channels": build_channels_diagnostics_info(module.get_channels()),
    }
    return data


def build_channels_diagnostics_info(channels: dict[str, Any]) -> dict[str, Any]:
    """Build diagnostics info for all channels."""
    data: dict[str, Any] = {}
    for channel in channels.values():
        data[channel.get_channel_number()] = {}
        for key, value in channel.__dict__.items():
            if key not in ["_module", "_writer", "_name_parts", "_on_status_update"]:
                data[channel.get_channel_number()][key.replace("_", "", 1)] = value
    return data
