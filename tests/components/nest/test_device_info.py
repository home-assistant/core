"""Test for properties for devices common to all entity types."""

from google_nest_sdm.device import Device

from homeassistant.components.nest.device_info import NestDeviceInfo
from homeassistant.helpers.device_registry import DeviceInfo


def test_device_custom_name() -> None:
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
    assert device_info.device_info == DeviceInfo(
        identifiers={("nest", "some-device-id")},
        name="My Doorbell",
        manufacturer="Google Nest",
        model="Doorbell",
        suggested_area=None,
    )


def test_device_name_room() -> None:
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
    assert device_info.device_info == DeviceInfo(
        identifiers={("nest", "some-device-id")},
        name="Some Room",
        manufacturer="Google Nest",
        model="Doorbell",
        suggested_area="Some Room",
    )


def test_device_no_name() -> None:
    """Test a device that has a name inferred from the type."""
    device = Device.MakeDevice(
        {"name": "some-device-id", "type": "sdm.devices.types.DOORBELL", "traits": {}},
        auth=None,
    )

    device_info = NestDeviceInfo(device)
    assert device_info.device_name == "Doorbell"
    assert device_info.device_model == "Doorbell"
    assert device_info.device_brand == "Google Nest"
    assert device_info.device_info == DeviceInfo(
        identifiers={("nest", "some-device-id")},
        name="Doorbell",
        manufacturer="Google Nest",
        model="Doorbell",
        suggested_area=None,
    )


def test_device_invalid_type() -> None:
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
    assert device_info.device_info == DeviceInfo(
        identifiers={("nest", "some-device-id")},
        name="My Doorbell",
        manufacturer="Google Nest",
        model=None,
        suggested_area=None,
    )


def test_suggested_area() -> None:
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
    assert device_info.device_info == DeviceInfo(
        identifiers={("nest", "some-device-id")},
        name="My Doorbell",
        manufacturer="Google Nest",
        model="Doorbell",
        suggested_area="Some Room",
    )
