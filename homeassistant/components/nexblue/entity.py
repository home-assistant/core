"""Common entity helpers for NexBlue."""

from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN


def charger_device_info(serial_number: str) -> DeviceInfo:
    """Return device information for a NexBlue charger."""
    return DeviceInfo(
        identifiers={(DOMAIN, serial_number)},
        manufacturer="NexBlue",
        name=serial_number,
        serial_number=serial_number,
    )
