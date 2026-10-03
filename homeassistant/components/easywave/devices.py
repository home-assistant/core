"""Device helpers for Easywave hub config entries."""

from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_DEVICES

from .const import CONF_DEVICE_TITLE, DEVICE_SUBENTRY_TYPES
from .entity import EasywaveDeviceEntry

if TYPE_CHECKING:
    from . import EasywaveConfigEntry


def iter_device_buckets(entry: EasywaveConfigEntry) -> Iterator[ConfigSubentry]:
    """Yield device bucket subentries for a gateway config entry."""
    for subentry_type in DEVICE_SUBENTRY_TYPES:
        yield from entry.get_subentries_of_type(subentry_type)


def _iter_devices_in_bucket(
    subentry: ConfigSubentry,
) -> Iterator[tuple[str, str, dict[str, Any]]]:
    """Yield device id, title and data stored in a bucket subentry."""
    devices = subentry.data.get(CONF_DEVICES)
    if not isinstance(devices, dict):
        return
    for device_id, device_data in devices.items():
        if not isinstance(device_data, dict):
            continue
        data = dict(device_data)
        title = str(data.pop(CONF_DEVICE_TITLE, device_id))
        yield device_id, title, data


def get_devices(entry: EasywaveConfigEntry) -> list[EasywaveDeviceEntry]:
    """Return configured child devices for a gateway config entry."""
    devices: list[EasywaveDeviceEntry] = []
    for subentry in iter_device_buckets(entry):
        if subentry.unique_id is None:
            continue
        for device_id, title, data in _iter_devices_in_bucket(subentry):
            devices.append(
                EasywaveDeviceEntry(
                    device_id=device_id,
                    title=title,
                    data=data,
                    subentry_id=subentry.subentry_id,
                )
            )
    return devices


def get_device_data(
    entry: EasywaveConfigEntry, device_id: str
) -> dict[str, Any] | None:
    """Return stored data for a child device identifier."""
    for subentry in iter_device_buckets(entry):
        for stored_id, _title, data in _iter_devices_in_bucket(subentry):
            if stored_id == device_id:
                return data
    return None
