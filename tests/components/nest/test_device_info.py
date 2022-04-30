"""Test for properties for devices common to all entity types."""

from google_nest_sdm.device import Device

from homeassistant.components.nest.device_info import NestDeviceInfo
from homeassistant.const import (
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
    ATTR_SUGGESTED_AREA,
)


def test_device_custom_name():
    """Test a device name from an Info trait."""
    device = Device.MakeDevice(
        {
            "name": "some-device-id",
            "type": "sdm.devices.types.DOORBELL",
            "traits": {
                "sdm.devices.traits.Info": {
                    "customName": "My Doorbell",
                },
            },
        },
        auth=None,
    )

    device_info = NestDeviceInfo(device)
    assert device_info.device_name == "My Doorbell"
    assert device_info.device_model == "Doorbell"
    assert device_info.device_brand == "Google Nest"
    assert device_info.device_info == {
        ATTR_IDENTIFIERS: {("nest", "some-device-id")},
        ATTR_NAME: "My Doorbell",
        ATTR_MANUFACTURER: "Google Nest",
        ATTR_MODEL: "Doorbell",
        ATTR_SUGGESTED_AREA: None,
    }


def test_device_name_room():
    """Test a device name from the room name."""
    device = Device.MakeDevice(
        {
            "name": "some-device-id",
            "type": "sdm.devices.types.DOORBELL",
            "parentRelations": [
                {"parent": "some-structure-id", "displayName": "Some Room"}
            ],
        },
        auth=None,
    )

    device_info = NestDeviceInfo(device)
    assert device_info.device_name == "Some Room"
    assert device_info.device_model == "Doorbell"
    assert device_info.device_brand == "Google Nest"
    assert device_info.device_info == {
        ATTR_IDENTIFIERS: {("nest", "some-device-id")},
        ATTR_NAME: "Some Room",
        ATTR_MANUFACTURER: "Google Nest",
        ATTR_MODEL: "Doorbell",
        ATTR_SUGGESTED_AREA: "Some Room",
    }


def test_device_no_name():
    """Test a device that has a name inferred from the type."""
    device = Device.MakeDevice(
        {"name": "some-device-id", "type": "sdm.devices.types.DOORBELL", "traits": {}},
        auth=None,
    )

    device_info = NestDeviceInfo(device)
    assert device_info.device_name == "Doorbell"
    assert device_info.device_model == "Doorbell"
    assert device_info.device_brand == "Google Nest"
    assert device_info.device_info == {
        ATTR_IDENTIFIERS: {("nest", "some-device-id")},
        ATTR_NAME: "Doorbell",
        ATTR_MANUFACTURER: "Google Nest",
        ATTR_MODEL: "Doorbell",
        ATTR_SUGGESTED_AREA: None,
    }


def test_device_invalid_type():
    """Test a device with a type name that is not recognized."""
    device = Device.MakeDevice(
        {
            "name": "some-device-id",
            "type": "sdm.devices.types.INVALID_TYPE",
            "traits": {
                "sdm.devices.traits.Info": {
                    "customName": "My Doorbell",
                },
            },
        },
        auth=None,
    )

    device_info = NestDeviceInfo(device)
    assert device_info.device_name == "My Doorbell"
    assert device_info.device_model is None
    assert device_info.device_brand == "Google Nest"
    assert device_info.device_info == {
        ATTR_IDENTIFIERS: {("nest", "some-device-id")},
        ATTR_NAME: "My Doorbell",
        ATTR_MANUFACTURER: "Google Nest",
        ATTR_MODEL: None,
        ATTR_SUGGESTED_AREA: None,
    }


def test_suggested_area():
    """Test the suggested area with different device name and room name."""
    device = Device.MakeDevice(
        {
            "name": "some-device-id",
            "type": "sdm.devices.types.DOORBELL",
            "traits": {
                "sdm.devices.traits.Info": {
                    "customName": "My Doorbell",
                },
            },
            "parentRelations": [
                {"parent": "some-structure-id", "displayName": "Some Room"}
            ],
        },
        auth=None,
    )

    device_info = NestDeviceInfo(device)
    assert device_info.device_name == "My Doorbell"
    assert device_info.device_model == "Doorbell"
    assert device_info.device_brand == "Google Nest"
    assert device_info.device_info == {
        ATTR_IDENTIFIERS: {("nest", "some-device-id")},
        ATTR_NAME: "My Doorbell",
        ATTR_MANUFACTURER: "Google Nest",
        ATTR_MODEL: "Doorbell",
        ATTR_SUGGESTED_AREA: "Some Room",
    }
