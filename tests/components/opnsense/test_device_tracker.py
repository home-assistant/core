"""The tests for the opnsense device tracker platform."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.device_tracker import legacy
from homeassistant.components.opnsense.const import CONF_API_SECRET, DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

ARP_RESPONSE = [
    {
        "hostname": "?",
        "ip-address": "192.168.0.123",
        "mac-address": "ff:ff:ff:ff:ff:ff",
        "interface": "igb1",
        "expires": 1199,
        "type": "ethernet",
    },
    {
        "hostname": "Desktop",
        "ip-address": "192.168.0.167",
        "mac-address": "ff:ff:ff:ff:ff:fe",
        "interface": "igb1",
        "expires": 1199,
        "type": "ethernet",
    },
]

INTERFACES_RESPONSE = {
    "igb0": {"name": "WAN", "interface": "igb0"},
    "igb1": {"name": "LAN", "interface": "igb1"},
}


@pytest.fixture(name="mock_opnsense_client")
def mock_opnsense_client_fixture() -> AsyncMock:
    """Mock for aiopnsense.OPNsenseClient."""
    with patch(
        "homeassistant.components.opnsense.OPNsenseClient",
    ) as mock_cls:
        client = mock_cls.return_value
        client.get_arp_table = AsyncMock(return_value=ARP_RESPONSE)
        client.get_interfaces = AsyncMock(return_value=INTERFACES_RESPONSE)
        yield client


async def test_get_scanner(
    hass: HomeAssistant,
    mock_opnsense_client: AsyncMock,
    mock_device_tracker_conf: list[legacy.Device],
) -> None:
    """Test creating an opnsense scanner."""
    result = await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                CONF_URL: "https://fake_host_fun/api",
                CONF_API_KEY: "fake_key",
                CONF_API_SECRET: "fake_secret",
                CONF_VERIFY_SSL: False,
            }
        },
    )
    await hass.async_block_till_done()
    assert result
    device_1 = hass.states.get("device_tracker.desktop")
    assert device_1 is not None
    assert device_1.state == "home"
    device_2 = hass.states.get("device_tracker.ff_ff_ff_ff_ff_ff")
    assert device_2.state == "home"
