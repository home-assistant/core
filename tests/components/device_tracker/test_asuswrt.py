"""The tests for the ASUSWRT device tracker platform."""
from homeassistant.components.asuswrt import (
    CONF_PROTOCOL, CONF_MODE, DOMAIN, CONF_PORT, DATA_ASUSWRT, async_setup)
from homeassistant.const import (CONF_PLATFORM, CONF_PASSWORD, CONF_USERNAME,
                                 CONF_HOST)

from tests.common import MockDependency, mock_coro_func

FAKEFILE = None

VALID_CONFIG_ROUTER_SSH = {DOMAIN: {
    CONF_PLATFORM: 'asuswrt',
    CONF_HOST: 'fake_host',
    CONF_USERNAME: 'fake_user',
    CONF_PROTOCOL: 'ssh',
    CONF_MODE: 'router',
    CONF_PORT: '22'
}}


async def test_password_or_pub_key_required(hass):
    """Test creating an AsusWRT scanner without a pass or pubkey."""
    with MockDependency('aioasuswrt.asuswrt')as mocked_asus:
        mocked_asus.AsusWrt().connection.async_connect = mock_coro_func()
        mocked_asus.AsusWrt().is_connected = False
        assert not await async_setup(
            hass, {DOMAIN: {
                CONF_PLATFORM: 'asuswrt',
                CONF_HOST: 'fake_host',
                CONF_USERNAME: 'fake_user'
            }})
        await hass.async_block_till_done()
        assert hass.data.get(DATA_ASUSWRT) is None


async def test_get_scanner_with_password_no_pubkey(hass):
    """Test creating an AsusWRT scanner with a password and no pubkey."""
    with MockDependency('aioasuswrt.asuswrt')as mocked_asus:
        mocked_asus.AsusWrt().connection.async_connect = mock_coro_func()
        mocked_asus.AsusWrt(
        ).connection.async_get_connected_devices = mock_coro_func(
            return_value={})
        assert await async_setup(
            hass, {DOMAIN: {
                CONF_PLATFORM: 'asuswrt',
                CONF_HOST: 'fake_host',
                CONF_USERNAME: 'fake_user',
                CONF_PASSWORD: '4321'
            }})
        await hass.async_block_till_done()
        assert hass.data[DATA_ASUSWRT] is not None
