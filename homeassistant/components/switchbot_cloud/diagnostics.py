"""Diagnostics support for SwitchBot Cloud."""

from dataclasses import fields
from typing import Any

from switchbot_api import Device, Remote

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import SwitchbotCloudConfigEntry
from .const import CONF_CLOUDHOOK_URL
from .coordinator import SwitchBotCoordinator

TO_REDACT = {"deviceId", "deviceMac", "hubDeviceId", "imageUrl"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SwitchbotCloudConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    devices: dict[str, tuple[Device | Remote, SwitchBotCoordinator, list[str]]] = {}
    for platform_field in fields(entry.runtime_data.devices):
        for device, coordinator in getattr(
            entry.runtime_data.devices, platform_field.name
        ):
            devices.setdefault(device.device_id, (device, coordinator, []))[2].append(
                platform_field.name
            )

    return {
        "webhook_registered": entry.runtime_data.webhook_registered,
        "cloudhook_configured": CONF_CLOUDHOOK_URL in entry.data,
        "devices": [
            {
                "device_type": device.device_type,
                "remote": isinstance(device, Remote),
                "platforms": platforms,
                "manageable_by_webhook": coordinator.manageable_by_webhook(),
                "last_update_success": coordinator.last_update_success,
                "status": async_redact_data(coordinator.data, TO_REDACT),
            }
            for device, coordinator, platforms in devices.values()
        ],
    }
