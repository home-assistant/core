"""Test the SFR Box diagnostics."""
from collections.abc import Generator
from unittest.mock import patch

import pytest

from homeassistant.components.diagnostics import REDACTED
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator

pytestmark = pytest.mark.usefixtures("system_get_info", "dsl_get_info")


@pytest.fixture(autouse=True)
def override_platforms() -> Generator[None, None, None]:
    """Override PLATFORMS."""
    with patch("homeassistant.components.sfr_box.PLATFORMS", []):
        yield


async def test_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry, hass_client: ClientSessionGenerator
) -> None:
    """Test config entry diagnostics."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert await get_diagnostics_for_config_entry(hass, hass_client, config_entry) == {
        "entry": {
            "data": {"host": "192.168.0.1"},
            "title": "Mock Title",
        },
        "data": {
            "dsl": {
                "attenuation_down": 28.5,
                "attenuation_up": 20.8,
                "counter": 16,
                "crc": 0,
                "line_status": "No Defect",
                "linemode": "ADSL2+",
                "noise_down": 5.8,
                "noise_up": 6.0,
                "rate_down": 5549,
                "rate_up": 187,
                "status": "up",
                "training": "Showtime",
                "uptime": 450796,
            },
            "system": {
                "alimvoltage": 12251,
                "current_datetime": "202212282233",
                "idur": "RP3P85K",
                "mac_addr": REDACTED,
                "net_infra": "adsl",
                "net_mode": "router",
                "product_id": "NB6VAC-FXC-r0",
                "refclient": "",
                "serial_number": REDACTED,
                "temperature": 27560,
                "uptime": 2353575,
                "version_bootloader": "NB6VAC-BOOTLOADER-R4.0.8",
                "version_dsldriver": "NB6VAC-XDSL-A2pv6F039p",
                "version_mainfirmware": "NB6VAC-MAIN-R4.0.44k",
                "version_rescuefirmware": "NB6VAC-MAIN-R4.0.44k",
            },
        },
    }
