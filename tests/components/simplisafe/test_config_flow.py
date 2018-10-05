"""Define tests for the SimpliSafe config flow."""
from unittest.mock import patch

from homeassistant import data_entry_flow
from homeassistant.components.simplisafe import DOMAIN, config_flow
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry, mock_coro


async def test_duplicate_error(hass):
    """Test that errors are shown when duplicates are added."""
    conf = {
        CONF_USERNAME: 'user@email.com',
        CONF_PASSWORD: 'password',
    }

    MockConfigEntry(domain=DOMAIN, data=conf).add_to_hass(hass)
    flow = config_flow.SimpliSafeFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=conf)
    assert result['errors'] == {'base': 'identifier_exists'}


async def test_invalid_credentials(hass):
    """Test that invalid credentials throws an error."""
    from simplipy.errors import SimplipyError
    conf = {
        CONF_USERNAME: 'user@email.com',
        CONF_PASSWORD: 'password',
    }

    flow = config_flow.SimpliSafeFlowHandler()
    flow.hass = hass

    with patch('simplipy.API.login_via_credentials',
               return_value=mock_coro(exception=SimplipyError)):
        result = await flow.async_step_user(user_input=conf)
        assert result['errors'] == {'base': 'invalid_credentials'}


async def test_show_form(hass):
    """Test that the form is served with no input."""
    flow = config_flow.SimpliSafeFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=None)

    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'user'
