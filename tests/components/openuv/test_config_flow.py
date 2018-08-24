"""Define tests for the OpenUV config flow."""

from homeassistant.components.openuv import config_flow
from homeassistant.const import (
    CONF_API_KEY, CONF_ELEVATION, CONF_LATITUDE, CONF_LONGITUDE)


async def test_step_import(hass):
    """Test that the config flow works."""
    conf = {
        CONF_API_KEY: '12345abcde',
    }

    flow = config_flow.OpenUvFlowHandler()
    flow.hass = hass

    result = await flow.async_step_import(import_config=conf)

    assert result['type'] == 'create_entry'
    assert result['title'] == '{0}, {1}'.format(
        hass.config.latitude, hass.config.longitude)
    assert result['data'] == conf


async def test_step_user(hass):
    """Test that the config flow works."""
    conf = {
        CONF_API_KEY: '12345abcde',
        CONF_ELEVATION: 59.1234,
        CONF_LATITUDE: 39.128712,
        CONF_LONGITUDE: -104.9812612,
    }

    flow = config_flow.OpenUvFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=conf)

    assert result['type'] == 'create_entry'
    assert result['title'] == '{0}, {1}'.format(
        conf[CONF_LATITUDE], conf[CONF_LONGITUDE])
    assert result['data'] == conf
