"""Tests for zone config flow."""

from homeassistant.components.zone import config_flow
from homeassistant.components.zone.const import CONF_PASSIVE, DOMAIN, HOME_ZONE
from homeassistant.const import (
    CONF_NAME, CONF_LATITUDE, CONF_LONGITUDE, CONF_ICON, CONF_RADIUS)

from tests.common import MockConfigEntry


async def test_flow_works(hass):
    """Test that config flow works."""
    flow = config_flow.ZoneFlowHandler()
    flow.hass = hass

    result = await flow.async_step_init(user_input={
        CONF_NAME: 'Name',
        CONF_LATITUDE: '1.1',
        CONF_LONGITUDE: '2.2',
        CONF_RADIUS: '100',
        CONF_ICON: 'mdi:home',
        CONF_PASSIVE: True
        })

    assert result['type'] == 'create_entry'
    assert result['title'] == 'Name'
    assert result['data'] == {
        CONF_NAME: 'Name',
        CONF_LATITUDE: '1.1',
        CONF_LONGITUDE: '2.2',
        CONF_RADIUS: '100',
        CONF_ICON: 'mdi:home',
        CONF_PASSIVE: True
    }


async def test_flow_requires_unique_name(hass):
    """Test that config flow verifies that each zones name is unique."""
    MockConfigEntry(domain=DOMAIN, data={
        CONF_NAME: 'Name'
    }).add_to_hass(hass)
    flow = config_flow.ZoneFlowHandler()
    flow.hass = hass

    result = await flow.async_step_init(user_input={CONF_NAME: 'Name'})
    assert result['errors'] == {'base': 'name_exists'}


async def test_flow_requires_name_different_from_home(hass):
    """Test that config flow verifies that each zones name is unique."""
    flow = config_flow.ZoneFlowHandler()
    flow.hass = hass

    result = await flow.async_step_init(user_input={CONF_NAME: HOME_ZONE})
    assert result['errors'] == {'base': 'name_exists'}
