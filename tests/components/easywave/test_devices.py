"""Tests for Easywave device storage helpers."""

from homeassistant.components.easywave.devices import get_devices

from .conftest import (
    MOCK_NEO_SENSOR_DEVICE_ID,
    MOCK_TRANSMITTER_DEVICE_ID,
    _entry_with_subentries,
    _neo_sensor_device_record,
    _transmitter_device_record,
)


def test_get_devices_returns_configured_subentries() -> None:
    """Configured device subentries are exposed as device views."""
    entry = _entry_with_subentries(
        _neo_sensor_device_record(title="Neo Sensor"),
        _transmitter_device_record(title="Transmitter"),
    )

    devices = get_devices(entry)
    assert len(devices) == 2
    assert {device.device_id for device in devices} == {
        MOCK_NEO_SENSOR_DEVICE_ID,
        MOCK_TRANSMITTER_DEVICE_ID,
    }
    assert {device.title for device in devices} == {"Neo Sensor", "Transmitter"}
    assert all(device.subentry_id for device in devices)


def test_get_devices_skips_buckets_without_unique_id() -> None:
    """Bucket subentries without a unique id are ignored."""
    entry = _entry_with_subentries(_transmitter_device_record())
    subentry = next(iter(entry.subentries.values()))
    object.__setattr__(subentry, "unique_id", None)

    assert get_devices(entry) == []
