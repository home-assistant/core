"""Tests for the Point config flow."""
from unittest.mock import Mock, patch

from homeassistant import data_entry_flow
from homeassistant.components.ambiclimate import config_flow
from tests.common import mock_coro


def init_config_flow(hass, valid_code=True):
    """Init a configuration flow."""
    config_flow.register_flow_implementation(hass, 'id', 'secret')
    flow = config_flow.AmbiclimateFlowHandler()

    flow._cb_url = Mock(  # pylint: disable=W0212
        return_value='https://hass.com',
    )
    flow._generate_view = Mock(  # pylint: disable=W0212
        return_value=mock_coro(None),
    )

    flow._generate_oauth = Mock(  # pylint: disable=W0212
        return_value=mock_coro(None),
    )

    flow._get_authorize_url = Mock(  # pylint: disable=W0212
        return_value=mock_coro('test'),
    )

    flow._get_token_info = Mock(  # pylint: disable=W0212
        return_value=mock_coro('token' if valid_code else None),
    )

    flow.hass = hass
    return flow


async def test_abort_if_no_implementation_registered(hass):
    """Test we abort if no implementation is registered."""
    flow = config_flow.AmbiclimateFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user()
    assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
    assert result['reason'] == 'no_config'


async def test_abort_if_already_setup(hass):
    """Test we abort if Ambiclimate is already setup."""
    flow = init_config_flow(hass)

    with patch.object(hass.config_entries, 'async_entries', return_value=[{}]):
        result = await flow.async_step_user()
    assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
    assert result['reason'] == 'already_setup'

    with patch.object(hass.config_entries, 'async_entries', return_value=[{}]):
        result = await flow.async_step_code()
    assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
    assert result['reason'] == 'already_setup'


async def test_full_flow_implementation(hass):
    """Test registering an implementation and finishing flow works."""
    config_flow.register_flow_implementation(hass, None, None)
    flow = init_config_flow(hass)

    result = await flow.async_step_user()
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'auth'
    assert result['description_placeholders']['cb_url'] == 'https://hass.com'
    assert result['description_placeholders']['authorization_url'] == 'test'

    result = await flow.async_step_code('123ABC')
    assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result['title'] == 'Ambiclimate'
    assert result['data']['callback_url'] == 'https://hass.com'
    assert result['data']['client_secret'] == 'secret'
    assert result['data']['client_id'] == 'id'


async def test_abort_no_code(hass):
    """Test if no code is given to step_code."""
    config_flow.register_flow_implementation(hass, None, None)
    flow = init_config_flow(hass, valid_code=False)

    result = await flow.async_step_code('invalid')
    assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
    assert result['reason'] == 'access_token'
