"""The tests for the opnsense device tracker platform."""

from unittest import mock

from homeassistant.components.opnsense import CONF_API_SECRET, DOMAIN
from homeassistant.const import CONF_URL, CONF_API_KEY, CONF_VERIFY_SSL
from homeassistant.setup import async_setup_component
import homeassistant.components.device_tracker as device_tracker

from tests.common import MockDependency


async def test_get_scanner(hass):
    """Test creating an opnsense scanner."""
    with MockDependency("pyopnsense") as mocked_opnsense:
        interface_client = mock.MagicMock()
        mocked_opnsense.diagnostics.InterfaceClient.return_value = interface_client
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
        mocked_opnsense.diagnostics.NetworkInsightClient = network_insight_client
        network_insight_client.get_interfaces.return_value = {
            "igb0": "WAN",
            "igb1": "LAN",
        }

        result = await async_setup_component(
            hass,
            device_tracker.DOMAIN,
            {
                DOMAIN: {
                    CONF_URL: "https://fake_host_fun/api",
                    CONF_API_KEY: "fake_key",
                    CONF_API_SECRET: "fake_secret",
                    CONF_VERIFY_SSL: False,
                }
            },
        )
        assert result
        device_1 = hass.states.get("device_tracker.desktop")
        assert device_1 is not None
        assert device_1.state == "not_home"
        device_2 = hass.states.get("device_tracker.ff_ff_ff_ff_ff_ff")
        assert device_2.state == "not_home"
