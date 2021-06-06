"""Test the Aurora ABB PowerOne Solar PV config flow."""

from aurorapy.client import AuroraSerialClient

from homeassistant.components.aurora_abb_powerone.aurora_device import AuroraDevice
from homeassistant.components.aurora_abb_powerone.const import (
    ATTR_DEVICE_NAME,
    ATTR_FIRMWARE,
    ATTR_MODEL,
    ATTR_SERIAL_NUMBER,
    DEFAULT_INTEGRATION_TITLE,
    DOMAIN,
    MANUFACTURER,
)
from homeassistant.config_entries import ConfigEntry


async def test_create_auroradevice(hass):
    """Test creation of an aurora abb powerone device."""
    client = AuroraSerialClient(7, "/dev/ttyUSB7", parity="N", timeout=1)
    config = ConfigEntry(
        version=1,
        domain=DOMAIN,
        title=DEFAULT_INTEGRATION_TITLE,
        data={
            ATTR_SERIAL_NUMBER: "65432",
            ATTR_MODEL: "AAYYBB",
            ATTR_DEVICE_NAME: "Feathers McGraw",
            ATTR_FIRMWARE: "0.1.2.3",
        },
        source="dummysource",
        entry_id="13579",
    )
    device = AuroraDevice(client, config.data)
    uid = device.unique_id
    assert uid == "65432_device"

    available = device.available
    assert available

    info = device.device_info
    assert info == {
        "identifiers": {(DOMAIN, "65432")},
        "manufacturer": MANUFACTURER,
        "model": "AAYYBB",
        "name": "Feathers McGraw",
        "sw_version": "0.1.2.3",
    }
