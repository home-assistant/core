"""The tests for the ASUSWRT device tracker platform."""
from unittest.mock import patch

from homeassistant.components.asuswrt import (
    CONF_MODE,
    CONF_PORT,
    CONF_PROTOCOL,
    DATA_ASUSWRT,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PLATFORM, CONF_USERNAME
from homeassistant.setup import async_setup_component

from tests.common import mock_coro_func

FAKEFILE = None

VALID_CONFIG_ROUTER_SSH = {
    DOMAIN: {
        CONF_PLATFORM: "asuswrt",
        CONF_HOST: "fake_host",
        CONF_USERNAME: "fake_user",
        CONF_PROTOCOL: "ssh",
        CONF_MODE: "router",
        CONF_PORT: "22",
    }
}


async def test_password_or_pub_key_required(hass):
    """Test creating an AsusWRT scanner without a pass or pubkey."""
    with patch("homeassistant.components.asuswrt.AsusWrt") as AsusWrt:
        AsusWrt().connection.async_connect = mock_coro_func()
        AsusWrt().is_connected = False
        result = await async_setup_component(
            hass, DOMAIN, {DOMAIN: {CONF_HOST: "fake_host", CONF_USERNAME: "fake_user"}}
        )
        assert not result


async def test_get_scanner_with_password_no_pubkey(hass):
    """Test creating an AsusWRT scanner with a password and no pubkey."""
    with patch("homeassistant.components.asuswrt.AsusWrt") as AsusWrt:
        AsusWrt().connection.async_connect = mock_coro_func()
        AsusWrt().connection.async_get_connected_devices = mock_coro_func(
            return_value={}
        )
        result = await async_setup_component(
            hass,
            DOMAIN,
            {
                DOMAIN: {
                    CONF_HOST: "fake_host",
                    CONF_USERNAME: "fake_user",
                    CONF_PASSWORD: "4321",
                }
            },
        )
        assert result
        assert hass.data[DATA_ASUSWRT] is not None
