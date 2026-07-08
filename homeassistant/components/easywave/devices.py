"""Device storage helpers for Easywave hub config entries."""

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from homeassistant.const import CONF_DEVICE_ID, CONF_DEVICES

from .const import CONF_DEVICE_DATA, CONF_DEVICE_TITLE
from .entity import EasywaveDeviceEntry

if TYPE_CHECKING:
    from . import EasywaveConfigEntry


def _device_from_stored(stored: Mapping[str, Any]) -> EasywaveDeviceEntry:
    """Return a device view from a stored device record."""
    return EasywaveDeviceEntry(
        device_id=stored[CONF_DEVICE_ID],
        title=stored[CONF_DEVICE_TITLE],
        data=dict(stored[CONF_DEVICE_DATA]),
    )


def get_stored_devices(entry: EasywaveConfigEntry) -> list[dict[str, Any]]:
    """Return raw device records stored on the config entry."""
    stored_devices = entry.options.get(CONF_DEVICES, [])
    if not isinstance(stored_devices, list):
        return []
    return [dict(stored) for stored in stored_devices if isinstance(stored, dict)]


def get_devices(entry: EasywaveConfigEntry) -> list[EasywaveDeviceEntry]:
    """Return configured child devices for a gateway config entry."""
    return [
        _device_from_stored(stored)
        for stored in get_stored_devices(entry)
        if CONF_DEVICE_ID in stored
        and CONF_DEVICE_TITLE in stored
        and CONF_DEVICE_DATA in stored
    ]
