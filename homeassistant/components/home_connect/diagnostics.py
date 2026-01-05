"""Diagnostics support for Home Connect Diagnostics."""

from __future__ import annotations

from typing import Any

from aiohomeconnect.model import GetSetting, Status

from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from .const import DOMAIN
from .coordinator import HomeConnectApplianceData, HomeConnectConfigEntry


def _serialize_item(item: Status | GetSetting) -> dict[str, Any]:
    """Serialize a status or setting item to a dictionary."""
    data = {"value": item.value}
    if item.unit is not None:
        data["unit"] = item.unit
    if item.constraints is not None:
        data["constraints"] = {
            k: v for k, v in item.constraints.to_dict().items() if v is not None
        }
    return data


async def _generate_appliance_diagnostics(
    appliance: HomeConnectApplianceData,
) -> dict[str, Any]:
    return {
        **appliance.info.to_dict(),
        "status": {
            key.value: _serialize_item(status)
            for key, status in appliance.status.items()
        },
        "settings": {
            key.value: _serialize_item(setting)
            for key, setting in appliance.settings.items()
        },
        "programs": [program.raw_key for program in appliance.programs],
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: HomeConnectConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return {
        appliance.info.ha_id: await _generate_appliance_diagnostics(appliance)
        for appliance in entry.runtime_data.data.values()
    }


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: HomeConnectConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device."""
    ha_id = next(
        (identifier[1] for identifier in device.identifiers if identifier[0] == DOMAIN),
    )
    return await _generate_appliance_diagnostics(entry.runtime_data.data[ha_id])
