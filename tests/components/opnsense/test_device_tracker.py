"""The tests for the opnsense device tracker platform."""
from unittest import mock

import pytest

from homeassistant.components import opnsense
from homeassistant.components.device_tracker import legacy
from homeassistant.components.opnsense import CONF_API_SECRET, DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


@pytest.fixture(name="mocked_opnsense")
def mocked_opnsense():
    """Mock for pyopnense.diagnostics."""
    with mock.patch.object(opnsense, "diagnostics") as mocked_opn:
        yield mocked_opn


async def test_get_scanner(
    hass: HomeAssistant, mocked_opnsense, mock_device_tracker_conf: list[legacy.Device]
) -> None:
    """Test creating an opnsense scanner."""
    interface_client = mock.MagicMock()
    mocked_opnsense.InterfaceClient.return_value = interface_client
    interface_client.get_arp.return_value = [
        {
            "hostname": "",
            "intf": "igb1",
            "intf_description": "LAN",
            "ip": "192.168.0.123",
            "mac": "ff:ff:ff:ff:ff:ff",
            "manufacturer": "",
        },
        {
            "hostname": "Desktop",
            "intf": "igb1",
            "intf_description": "LAN",
            "ip": "192.168.0.167",
            "mac": "ff:ff:ff:ff:ff:fe",
            "manufacturer": "OEM",
        },
    ]
    network_insight_client = mock.MagicMock()
    mocked_opnsense.NetworkInsightClient.return_value = network_insight_client
    network_insight_client.get_interfaces.return_value = {"igb0": "WAN", "igb1": "LAN"}

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
