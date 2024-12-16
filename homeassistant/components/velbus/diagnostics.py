"""Diagnostics support for Velbus."""

from __future__ import annotations

from typing import Any

from velbusaio.channels import Channel as VelbusChannel
from velbusaio.module import Module as VelbusModule

from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from . import VelbusConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: VelbusConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    controller = entry.runtime_data.controller
    data: dict[str, Any] = {"entry": entry.as_dict(), "modules": []}
    for module in controller.get_modules().values():
        data["modules"].append(_build_module_diagnostics_info(module))
    return data


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: VelbusConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device entry."""
    controller = entry.runtime_data.controller
    channel = list(next(iter(device.identifiers)))[1]
    modules = controller.get_modules()
    return _build_module_diagnostics_info(modules[int(channel)])


def _build_module_diagnostics_info(module: VelbusModule) -> dict[str, Any]:
    """Build per module diagnostics info."""
    data: dict[str, Any] = {
        "type": module.get_type_name(),
        "address": module.get_addresses(),
        "name": module.get_name(),
        "sw_version": module.get_sw_version(),
        "is_loaded": module.is_loaded(),
        "channels": _build_channels_diagnostics_info(module.get_channels()),
    }
    return data


def _build_channels_diagnostics_info(
    channels: dict[str, VelbusChannel],
) -> dict[str, Any]:
    """Build diagnostics info for all channels."""
    data: dict[str, Any] = {}
    for channel in channels.values():
        data[str(channel.get_channel_number())] = channel.get_channel_info()
    return data
