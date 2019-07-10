"""Define tests for the WWLLN config flow."""
from homeassistant import data_entry_flow
from homeassistant.components.wwlln import CONF_WINDOW, DOMAIN, config_flow
from homeassistant.const import (
    CONF_LATITUDE, CONF_LONGITUDE, CONF_RADIUS, CONF_UNIT_SYSTEM)

from tests.common import MockConfigEntry


async def test_duplicate_error(hass):
    """Test that errors are shown when duplicates are added."""
    conf = {
        CONF_LATITUDE: 39.128712,
        CONF_LONGITUDE: -104.9812612,
        CONF_RADIUS: 25,
    }

    MockConfigEntry(domain=DOMAIN, data=conf).add_to_hass(hass)
    flow = config_flow.WWLLNFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=conf)
    assert result['errors'] == {'base': 'identifier_exists'}


async def test_show_form(hass):
    """Test that the form is served with no input."""
    flow = config_flow.WWLLNFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=None)

    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'user'


async def test_step_import(hass):
    """Test that the import step works."""
    conf = {
        CONF_LATITUDE: 39.128712,
        CONF_LONGITUDE: -104.9812612,
        CONF_RADIUS: 25,
        CONF_UNIT_SYSTEM: 'metric',
        CONF_WINDOW: 600.0,
    }

    flow = config_flow.WWLLNFlowHandler()
    flow.hass = hass

    result = await flow.async_step_import(import_config=conf)
    assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result['title'] == '39.128712, -104.9812612'
    assert result['data'] == {
        CONF_LATITUDE: 39.128712,
        CONF_LONGITUDE: -104.9812612,
        CONF_RADIUS: 25,
        CONF_UNIT_SYSTEM: 'metric',
        CONF_WINDOW: 600.0,
    }


async def test_step_user(hass):
    """Test that the user step works."""
    conf = {
        CONF_LATITUDE: 39.128712,
        CONF_LONGITUDE: -104.9812612,
        CONF_RADIUS: 25,
    }

    flow = config_flow.WWLLNFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=conf)
    assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result['title'] == '39.128712, -104.9812612'
    assert result['data'] == {
        CONF_LATITUDE: 39.128712,
        CONF_LONGITUDE: -104.9812612,
        CONF_RADIUS: 25,
        CONF_UNIT_SYSTEM: 'metric',
        CONF_WINDOW: 600.0,
    }


async def test_custom_window(hass):
    """Test that a custom window is stored correctly."""
    conf = {
        CONF_LATITUDE: 39.128712,
        CONF_LONGITUDE: -104.9812612,
        CONF_RADIUS: 25,
        CONF_WINDOW: 300
    }

    flow = config_flow.WWLLNFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=conf)
    assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result['title'] == '39.128712, -104.9812612'
    assert result['data'] == {
        CONF_LATITUDE: 39.128712,
        CONF_LONGITUDE: -104.9812612,
        CONF_RADIUS: 25,
        CONF_UNIT_SYSTEM: 'metric',
        CONF_WINDOW: 300,
    }
