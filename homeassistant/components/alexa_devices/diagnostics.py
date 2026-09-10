"""Diagnostics support for Alexa Devices integration."""

from dataclasses import asdict
from typing import TYPE_CHECKING, Any

from aioamazondevices.structures import AmazonDevice

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import AnyDeviceEntry, DeviceEntry

from .coordinator import AmazonConfigEntry

TO_REDACT = {
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    "access_token",
    "adp_token",
    "device_private_key",
    "refresh_token",
    "store_authentication_cookie",
    "title",
    "website_cookies",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: AmazonConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    coordinator = entry.runtime_data

    devices: list[dict[str, dict[str, Any]]] = [
        build_device_data(device) for device in coordinator.data.values()
    ]

    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "device_info": {
            "last_update success": coordinator.last_update_success,
            "last_exception": repr(coordinator.last_exception),
            "devices": devices,
        },
    }


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: AmazonConfigEntry, device_entry: AnyDeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device."""

    coordinator = entry.runtime_data

    if TYPE_CHECKING:
        # alexa_devices does not create child devices, and devices have a serial number
        assert isinstance(device_entry, DeviceEntry)
        assert device_entry.serial_number

    return build_device_data(coordinator.data[device_entry.serial_number])


def build_device_data(device: AmazonDevice) -> dict[str, Any]:
    """Build device data for diagnostics."""
    return {
        "account name": device.account_name,
        "capabilities": device.capabilities,
        "device family": device.device_family,
        "device type": device.device_type,
        "device cluster members": device.device_cluster_members,
        "online": device.online,
        "serial number": device.serial_number,
        "software version": device.software_version,
        "sensors": {key: asdict(sensor) for key, sensor in device.sensors.items()},
    }
