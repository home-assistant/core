"""The tests for the ASUSWRT sensor platform."""
from unittest.mock import patch

# import homeassistant.components.sensor as sensor
from homeassistant.components.asuswrt import (
    CONF_DNSMASQ,
    CONF_INTERFACE,
    CONF_MODE,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_SENSORS,
    DATA_ASUSWRT,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.setup import async_setup_component

from tests.common import mock_coro_func

VALID_CONFIG_ROUTER_SSH = {
    DOMAIN: {
        CONF_DNSMASQ: "/",
        CONF_HOST: "fake_host",
        CONF_INTERFACE: "eth0",
        CONF_MODE: "router",
        CONF_PORT: "22",
        CONF_PROTOCOL: "ssh",
        CONF_USERNAME: "fake_user",
        CONF_PASSWORD: "fake_pass",
        CONF_SENSORS: "upload",
    }
}


async def test_default_sensor_setup(hass):
    """Test creating an AsusWRT sensor."""
    with patch("homeassistant.components.asuswrt.AsusWrt") as AsusWrt:
        AsusWrt().connection.async_connect = mock_coro_func()

        result = await async_setup_component(hass, DOMAIN, VALID_CONFIG_ROUTER_SSH)
        assert result
        assert hass.data[DATA_ASUSWRT] is not None
