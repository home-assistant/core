"""The tests for the ASUSWRT device tracker platform."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.asuswrt import (
    CONF_DNSMASQ,
    CONF_INTERFACE,
    DATA_ASUSWRT,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.setup import async_setup_component


async def test_password_or_pub_key_required(hass):
    """Test creating an AsusWRT scanner without a pass or pubkey."""
    with patch("homeassistant.components.asuswrt.AsusWrt") as AsusWrt:
        AsusWrt().connection.async_connect = AsyncMock()
        AsusWrt().is_connected = False
        result = await async_setup_component(
            hass, DOMAIN, {DOMAIN: {CONF_HOST: "fake_host", CONF_USERNAME: "fake_user"}}
        )
        assert not result


async def test_network_unreachable(hass):
    """Test creating an AsusWRT scanner without a pass or pubkey."""
    with patch("homeassistant.components.asuswrt.AsusWrt") as AsusWrt:
        AsusWrt().connection.async_connect = AsyncMock(side_effect=OSError)
        AsusWrt().is_connected = False
        result = await async_setup_component(
            hass, DOMAIN, {DOMAIN: {CONF_HOST: "fake_host", CONF_USERNAME: "fake_user"}}
        )
        assert result
        assert hass.data.get(DATA_ASUSWRT) is None


async def test_get_scanner_with_password_no_pubkey(hass):
    """Test creating an AsusWRT scanner with a password and no pubkey."""
    with patch("homeassistant.components.asuswrt.AsusWrt") as AsusWrt:
        AsusWrt().connection.async_connect = AsyncMock()
        AsusWrt().connection.async_get_connected_devices = AsyncMock(return_value={})
        result = await async_setup_component(
            hass,
            DOMAIN,
            {
                DOMAIN: {
                    CONF_HOST: "fake_host",
                    CONF_USERNAME: "fake_user",
                    CONF_PASSWORD: "4321",
                    CONF_DNSMASQ: "/",
                }
            },
        )
        assert result
        assert hass.data[DATA_ASUSWRT] is not None


async def test_specify_non_directory_path_for_dnsmasq(hass):
    """Test creating an AsusWRT scanner with a dnsmasq location which is not a valid directory."""
    with patch("homeassistant.components.asuswrt.AsusWrt") as AsusWrt:
        AsusWrt().connection.async_connect = AsyncMock()
        AsusWrt().is_connected = False
        result = await async_setup_component(
            hass,
            DOMAIN,
            {
                DOMAIN: {
                    CONF_HOST: "fake_host",
                    CONF_USERNAME: "fake_user",
                    CONF_PASSWORD: "4321",
                    CONF_DNSMASQ: 1234,
                }
            },
        )
        assert not result


async def test_interface(hass):
    """Test creating an AsusWRT scanner using interface eth1."""
    with patch("homeassistant.components.asuswrt.AsusWrt") as AsusWrt:
        AsusWrt().connection.async_connect = AsyncMock()
        AsusWrt().connection.async_get_connected_devices = AsyncMock(return_value={})
        result = await async_setup_component(
            hass,
            DOMAIN,
            {
                DOMAIN: {
                    CONF_HOST: "fake_host",
                    CONF_USERNAME: "fake_user",
                    CONF_PASSWORD: "4321",
                    CONF_DNSMASQ: "/",
                    CONF_INTERFACE: "eth1",
                }
            },
        )
        assert result
        assert hass.data[DATA_ASUSWRT] is not None


async def test_no_interface(hass):
    """Test creating an AsusWRT scanner using no interface."""
    with patch("homeassistant.components.asuswrt.AsusWrt") as AsusWrt:
        AsusWrt().connection.async_connect = AsyncMock()
        AsusWrt().is_connected = False
        result = await async_setup_component(
            hass,
            DOMAIN,
            {
                DOMAIN: {
                    CONF_HOST: "fake_host",
                    CONF_USERNAME: "fake_user",
                    CONF_PASSWORD: "4321",
                    CONF_DNSMASQ: "/",
                    CONF_INTERFACE: None,
                }
            },
        )
        assert not result
