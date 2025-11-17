"""Test Connect ZBT-2 utilities."""

from homeassistant.components.homeassistant_connect_zbt2.const import DOMAIN
from homeassistant.components.homeassistant_connect_zbt2.util import (
    get_usb_service_info,
)
from homeassistant.helpers.service_info.usb import UsbServiceInfo

from tests.common import MockConfigEntry

CONNECT_ZBT2_CONFIG_ENTRY = MockConfigEntry(
    domain=DOMAIN,
    unique_id="some_unique_id",
    data={
        "device": "/dev/serial/by-id/usb-Nabu_Casa_ZBT-2_80B54EEFAE18-if01-port0",
        "vid": "303A",
        "pid": "4001",
        "serial_number": "80B54EEFAE18",
        "manufacturer": "Nabu Casa",
        "product": "ZBT-2",
        "firmware": "ezsp",
    },
    version=2,
)


def test_get_usb_service_info() -> None:
    """Test `get_usb_service_info` conversion."""
    assert get_usb_service_info(CONNECT_ZBT2_CONFIG_ENTRY) == UsbServiceInfo(
        device=CONNECT_ZBT2_CONFIG_ENTRY.data["device"],
        vid=CONNECT_ZBT2_CONFIG_ENTRY.data["vid"],
        pid=CONNECT_ZBT2_CONFIG_ENTRY.data["pid"],
        serial_number=CONNECT_ZBT2_CONFIG_ENTRY.data["serial_number"],
        manufacturer=CONNECT_ZBT2_CONFIG_ENTRY.data["manufacturer"],
        description=CONNECT_ZBT2_CONFIG_ENTRY.data["product"],
    )
