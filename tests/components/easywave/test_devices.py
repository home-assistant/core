"""Tests for Easywave device storage helpers."""

from homeassistant.components.easywave.const import (
    CONF_DEVICE_TITLE,
    CONF_ENTRY_TYPE,
    CONF_TRANSMITTER_SERIAL,
    ENTRY_TYPE_TRANSMITTER,
    SUBENTRY_TYPE_EASYWAVE_TRANSMITTER,
)
from homeassistant.components.easywave.devices import get_devices
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_DEVICES

from .conftest import (
    MOCK_NEO_SENSOR_DEVICE_ID,
    MOCK_TRANSMITTER_DEVICE_ID,
    MOCK_TRANSMITTER_SERIAL,
    _bucket_subentry_data,
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


def test_get_devices_skips_invalid_bucket_entries() -> None:
    """Malformed bucket data does not break device enumeration."""
    valid_device = {
        CONF_DEVICE_TITLE: "Transmitter",
        CONF_ENTRY_TYPE: ENTRY_TYPE_TRANSMITTER,
        CONF_TRANSMITTER_SERIAL: MOCK_TRANSMITTER_SERIAL,
    }
    entry = _entry_with_subentries(
        ConfigSubentryData(
            data={CONF_DEVICES: "invalid"},
            subentry_type=SUBENTRY_TYPE_EASYWAVE_TRANSMITTER,
            title="Easywave transmitter",
            unique_id="bucket_transmitter",
        ),
        _bucket_subentry_data(
            subentry_type=SUBENTRY_TYPE_EASYWAVE_TRANSMITTER,
            devices={
                "invalid_device": "invalid",
                MOCK_TRANSMITTER_DEVICE_ID: valid_device,
            },
        ),
    )

    devices = get_devices(entry)
    assert len(devices) == 1
    assert devices[0].device_id == MOCK_TRANSMITTER_DEVICE_ID
