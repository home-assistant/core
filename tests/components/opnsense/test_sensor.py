"""The tests for the opnsense sensor platform."""

from unittest import mock

import pytest

from homeassistant.components import opnsense
from homeassistant.components.opnsense.const import (
    CONF_API_SECRET,
    CONF_GATEWAY,
    DOMAIN,
)
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
from homeassistant.setup import async_setup_component


@pytest.fixture(name="mocked_opnsense")
def mocked_opnsense():
    """Mock for pyopnense.diagnostics."""
    with mock.patch.object(opnsense, "diagnostics") as mocked_opn:
        yield mocked_opn


async def test_get_gateway_sensor(hass, mocked_opnsense):
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

    with mock.patch.object(opnsense, "routes") as mocked_gateways:
        gateways_client = mock.MagicMock()
        mocked_gateways.GatewayClient.return_value = gateways_client
        gateways_client.status.return_value = {
            "items": [
                {
                    "name": "WAN",
                    "address": "127.0.0.1",
                    "status": "none",
                    "loss": "3.14 %",
                    "delay": "42.0 ms",
                    "stddev": "0.1 ms",
                    "status_translated": "Online",
                },
            ],
            "status": "ok",
        }

        result = await async_setup_component(
            hass,
            DOMAIN,
            {
                DOMAIN: {
                    CONF_URL: "https://fake_host_fun/api",
                    CONF_API_KEY: "fake_key",
                    CONF_API_SECRET: "fake_secret",
                    CONF_VERIFY_SSL: False,
                    CONF_GATEWAY: ["WAN"],
                }
            },
        )
        await hass.async_block_till_done()
        assert result
        gateway = hass.states.get("sensor.gateway_wan")
        assert gateway is not None
        assert gateway.state == "Online"
