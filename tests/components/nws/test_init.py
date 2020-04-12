"""Tests for init module."""
from homeassistant.components import nws
from homeassistant.components.nws.const import CONF_STATION, DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.setup import async_setup_component

from tests.common import assert_setup_component
from tests.components.nws.const import MINIMAL_CONFIG

LATLON_CONFIG = {
    DOMAIN: [{CONF_API_KEY: "test", CONF_LATITUDE: 45.0, CONF_LONGITUDE: -75.0}]
}
FULL_CONFIG = {
    DOMAIN: [
        {
            CONF_API_KEY: "test",
            CONF_LATITUDE: 45.0,
            CONF_LONGITUDE: -75.0,
            CONF_STATION: "XYZ",
        }
    ]
}
DUPLICATE_CONFIG = {
    DOMAIN: [
        {CONF_API_KEY: "test", CONF_LATITUDE: 45.0, CONF_LONGITUDE: -75.0},
        {CONF_API_KEY: "test", CONF_LATITUDE: 45.0, CONF_LONGITUDE: -75.0},
    ]
}


async def test_no_config(hass, mock_simple_nws):
    """Test that nws does not setup with no config."""
    with assert_setup_component(0):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        entity_registry = await hass.helpers.entity_registry.async_get_registry()
        assert len(entity_registry.entities) == 0

        assert DOMAIN not in hass.data


async def test_successful_minimal_config(hass, mock_simple_nws):
    """Test that nws setup with minimal config."""
    hass.config.latitude = 40.0
    hass.config.longitude = -75.0
    with assert_setup_component(1, DOMAIN):
        assert await async_setup_component(hass, DOMAIN, MINIMAL_CONFIG)
        await hass.async_block_till_done()

        entity_registry = await hass.helpers.entity_registry.async_get_registry()
        assert len(entity_registry.entities) == 2

        assert DOMAIN in hass.data
        assert nws.base_unique_id(40.0, -75.0) in hass.data[DOMAIN]


async def test_successful_latlon_config(hass, mock_simple_nws):
    """Test that nws setup with latlon config."""
    with assert_setup_component(1, DOMAIN):
        assert await async_setup_component(hass, DOMAIN, LATLON_CONFIG)
        await hass.async_block_till_done()

        entity_registry = await hass.helpers.entity_registry.async_get_registry()
        assert len(entity_registry.entities) == 2

        assert DOMAIN in hass.data
        assert nws.base_unique_id(45.0, -75.0) in hass.data[DOMAIN]


async def test_successful_full_config(hass, mock_simple_nws):
    """Test that nws setup with full config."""
    with assert_setup_component(1, DOMAIN):
        assert await async_setup_component(hass, DOMAIN, FULL_CONFIG)
        await hass.async_block_till_done()

        entity_registry = await hass.helpers.entity_registry.async_get_registry()
        assert len(entity_registry.entities) == 2

        assert DOMAIN in hass.data
        assert nws.base_unique_id(45.0, -75.0) in hass.data[DOMAIN]


async def test_unsuccessful_duplicate_config(hass, mock_simple_nws):
    """Test that nws setup with duplicate config."""
    assert await async_setup_component(hass, DOMAIN, DUPLICATE_CONFIG)
    await hass.async_block_till_done()

    entity_registry = await hass.helpers.entity_registry.async_get_registry()
    assert len(entity_registry.entities) == 2

    assert len(hass.data[DOMAIN]) == 1
