"""Test the SensorPush config flow."""

from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

HTW_SERVICE_INFO = BluetoothServiceInfo(
    name="SensorPush HT.w 0CA1",
    address="61DE521B-F0BF-9F44-64D4-75BBE1738105",
    rssi=-63,
    manufacturer_data={11271: b"\xfe\x00\x01"},
    service_data={},
    service_uuids=["ef090000-11d6-42ba-93b8-9dd7ec090ab0"],
    source="local",
)
HTPWX_SERVICE_INFO = BluetoothServiceInfo(
    name="SensorPush HTP.xw F4D",
    address="4125DDBA-2774-4851-9889-6AADDD4CAC3D",
    rssi=-56,
    manufacturer_data={7168: b"\xcd=!\xd1\xb9"},
    service_data={},
    service_uuids=["ef090000-11d6-42ba-93b8-9dd7ec090ab0"],
    source="local",
)


def test_async_step_bluetooth(hass):
    """Test discovery via bluetooth."""
