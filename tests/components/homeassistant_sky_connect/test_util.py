"""Test SkyConnect utilities."""

from homeassistant.components.homeassistant_sky_connect.const import (
    DOMAIN,
    HardwareVariant,
)
from homeassistant.components.homeassistant_sky_connect.util import (
    get_hardware_variant,
    get_usb_service_info,
)
from homeassistant.helpers.service_info.usb import UsbServiceInfo

from tests.common import MockConfigEntry

SKYCONNECT_CONFIG_ENTRY = MockConfigEntry(
    domain=DOMAIN,
    unique_id="some_unique_id",
    data={
        "device": "/dev/serial/by-id/usb-Nabu_Casa_SkyConnect_v1.0_9e2adbd75b8beb119fe564a0f320645d-if00-port0",
        "vid": "10C4",
        "pid": "EA60",
        "serial_number": "3c0ed67c628beb11b1cd64a0f320645d",
        "manufacturer": "Nabu Casa",
        "product": "SkyConnect v1.0",
        "firmware": "ezsp",
    },
    version=2,
)

CONNECT_ZBT1_CONFIG_ENTRY = MockConfigEntry(
    domain=DOMAIN,
    unique_id="some_unique_id",
    data={
        "device": "/dev/serial/by-id/usb-Nabu_Casa_Home_Assistant_Connect_ZBT-1_9e2adbd75b8beb119fe564a0f320645d-if00-port0",
        "vid": "10C4",
        "pid": "EA60",
        "serial_number": "3c0ed67c628beb11b1cd64a0f320645d",
        "manufacturer": "Nabu Casa",
        "product": "Home Assistant Connect ZBT-1",
        "firmware": "ezsp",
    },
    version=2,
)


def test_get_usb_service_info() -> None:
    """Test `get_usb_service_info` conversion."""
    assert get_usb_service_info(SKYCONNECT_CONFIG_ENTRY) == UsbServiceInfo(
        device=SKYCONNECT_CONFIG_ENTRY.data["device"],
        vid=SKYCONNECT_CONFIG_ENTRY.data["vid"],
        pid=SKYCONNECT_CONFIG_ENTRY.data["pid"],
        serial_number=SKYCONNECT_CONFIG_ENTRY.data["serial_number"],
        manufacturer=SKYCONNECT_CONFIG_ENTRY.data["manufacturer"],
        description=SKYCONNECT_CONFIG_ENTRY.data["product"],
    )


def test_get_hardware_variant() -> None:
    """Test `get_hardware_variant` extraction."""
    assert get_hardware_variant(SKYCONNECT_CONFIG_ENTRY) == HardwareVariant.SKYCONNECT
    assert (
        get_hardware_variant(CONNECT_ZBT1_CONFIG_ENTRY) == HardwareVariant.CONNECT_ZBT1
    )
