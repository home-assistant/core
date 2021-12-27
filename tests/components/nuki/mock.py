"""Mockup Nuki device."""

from tests.common import MockConfigEntry

NAME = "Nuki_Bridge_75BCD15"
HOST = "1.1.1.1"
MAC = "01:23:45:67:89:ab"

HW_ID = 123456789
ID_HEX = "75BCD15"

MOCK_INFO = {"ids": {"hardwareId": HW_ID}}


async def setup_nuki_integration(hass):
    """Create the Nuki device."""

    entry = MockConfigEntry(
        domain="nuki",
        unique_id=ID_HEX,
        data={"host": HOST, "port": 8080, "token": "test-token"},
    )
    entry.add_to_hass(hass)

    return entry
