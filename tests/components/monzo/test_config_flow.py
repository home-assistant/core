"""Define tests for the Monzo config flow."""

from homeassistant import data_entry_flow
from homeassistant.components.monzo import DOMAIN, config_flow
from homeassistant.const import (
    CONF_CLIENT_ID, CONF_CLIENT_SECRET)

from tests.common import MockConfigEntry


async def test_duplicate_error(hass):
    """Test that errors are shown when duplicates are added."""
    conf = {
        CONF_CLIENT_ID: 'test_client_id',
        CONF_CLIENT_SECRET: 'test_client_secret',
    }

    MockConfigEntry(domain=DOMAIN, data=conf).add_to_hass(hass)
    flow = config_flow.MonzoFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=conf)
    assert result['errors'] == {'base': 'identifier_exists'}


async def test_show_form(hass):
    """Test that the form is served with no input."""
    flow = config_flow.MonzoFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=None)

    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'user'

async def test_step_user(hass):
    """Test that the user step correctly calls link step."""
    conf = {
        CONF_CLIENT_ID: 'test_client_id',
        CONF_CLIENT_SECRET: 'test_client_secret',
    }

    flow = config_flow.MonzoFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=conf)

    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'link'
