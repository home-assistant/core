"""Test init of TCP integration."""
from copy import deepcopy

from homeassistant.components.tcp import DOMAIN
import homeassistant.components.tcp.common as tcp
from homeassistant.setup import async_setup_component

from .conftest import TEST_CONFIG

from tests.common import assert_setup_component

KEYS_AND_DEFAULTS = {
    tcp.CONF_TIMEOUT: tcp.DEFAULT_TIMEOUT,
    tcp.CONF_BUFFER_SIZE: tcp.DEFAULT_BUFFER_SIZE,
}


async def test_setup_platform_valid_config(hass, mock_socket):
    """Check a valid configuration and call add_entities with sensor."""
    with assert_setup_component(1, DOMAIN):
        assert await async_setup_component(hass, DOMAIN, TEST_CONFIG)
        await hass.async_block_till_done()


async def test_setup_platform_invalid_config(hass, mock_socket):
    """Check an invalid configuration."""
    with assert_setup_component(0):
        assert not await async_setup_component(
            hass, DOMAIN, {DOMAIN: {"host": "test_host", "porrt": 1234}}
        )
        await hass.async_block_till_done()


async def test_config_uses_defaults(hass, mock_socket):
    """Check if defaults were set."""
    config = deepcopy(TEST_CONFIG)

    for key in KEYS_AND_DEFAULTS:
        del config[DOMAIN][0][key]

    with assert_setup_component(1, DOMAIN) as result_config:
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    for key, default in KEYS_AND_DEFAULTS.items():
        assert result_config[DOMAIN][0].get(key) == default
