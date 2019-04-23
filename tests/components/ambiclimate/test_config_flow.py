"""Tests for the Ambiclimate config flow."""
from unittest.mock import Mock, patch

from homeassistant import data_entry_flow
from homeassistant.components.ambiclimate import config_flow
from homeassistant.setup import async_setup_component
from homeassistant.util import aiohttp
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


async def test_cb_url(hass):
    """Test callback function."""
    hass.config.api = Mock(base_url='http://example.com')
    flow = config_flow.AmbiclimateFlowHandler()
    flow.hass = hass
    assert flow._cb_url() == 'http://example.com/api/ambiclimate'


async def test_get_authorize_url(hass):
    """Test authorize url."""
    hass.config.api = Mock(base_url='http://example.com')

    config = {config_flow.CONF_CLIENT_ID: 'client_id',
              config_flow.CONF_CLIENT_SECRET: 'client_secret',
              }
    hass.data[config_flow.DATA_AMBICLIMATE_IMPL] = config
    flow = config_flow.AmbiclimateFlowHandler()
    flow.hass = hass
    url = await flow._get_authorize_url()  # pylint: disable=W0212
    assert 'https://api.ambiclimate.com/oauth2/authorize' in url
    assert 'client_id=client_id' in url
    assert 'response_type=code' in url
    assert 'redirect_uri=http%3A%2F%2Fexample.com%2Fapi%2Fambiclimate' in url


async def test_generate_view(hass):
    """Test generate view."""
    await async_setup_component(hass, 'http', {
        'http': {
            'base_url': 'example.com'
        }
    })

    flow = config_flow.AmbiclimateFlowHandler()
    flow.hass = hass
    await flow._generate_view()  # pylint: disable=W0212
    assert flow._registered_view  # pylint: disable=W0212


async def test_view(hass):
    """Test view."""
    hass.config_entries.flow.async_init = Mock()

    request = aiohttp.MockRequest(b'', query_string='code=test_code')
    request.app = {'hass': hass}
    view = config_flow.AmbiclimateAuthCallbackView()
    assert await view.get(request) == 'OK!'

    request = aiohttp.MockRequest(b'', query_string='')
    request.app = {'hass': hass}
    view = config_flow.AmbiclimateAuthCallbackView()
    assert await view.get(request) == 'No code'
