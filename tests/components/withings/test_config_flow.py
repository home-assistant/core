"""Tests for the Withings config flow."""
from aiohttp.web_request import BaseRequest
from asynctest import MagicMock, patch
import callee
import nokia
import pytest

from homeassistant import data_entry_flow, setup
import homeassistant.components.api as api
import homeassistant.components.http as http
from homeassistant.components.withings import (
    const
)
from homeassistant.components.withings.config_flow import (
    DATA_FLOW_IMPL,
    register_flow_implementation,
    WithingsFlowHandler,
    WithingsAuthCallbackView,
)
from homeassistant.config_entries import ConfigEntry


@pytest.fixture(name='flow_handler')
def flow_handler_fixture(hass):
    """Provide flow handler."""
    flow_handler = WithingsFlowHandler()
    flow_handler.hass = hass
    return flow_handler


@pytest.fixture(name='setup_hass')
async def setup_hass_fixture(hass):
    """Provide hass instance."""
    config = {
        http.DOMAIN: {},
        api.DOMAIN: {
            'base_url': 'http://localhost/'
        },
        const.DOMAIN: {
            const.CLIENT_ID: 'my_client_id',
            const.CLIENT_SECRET: 'my_secret',
            const.PROFILES: [
                'Person 1',
                'Person 2',
            ]
        }
    }

    hass.data = {}

    await setup.async_setup_component(hass, 'http', config)
    await setup.async_setup_component(hass, 'api', config)

    return hass


def test_flow_handler_init(flow_handler):
    """Test the init of the flow handler."""
    assert not flow_handler.flow_profile


def test_flow_handler_async_profile_config_entry(hass, flow_handler):
    """Test profile config entry."""
    config_entries = [
        ConfigEntry(
            1, const.DOMAIN, 'AAA', {}, 'source', 'connection_class'
        ),
        ConfigEntry(
            1, const.DOMAIN, 'Person 1', {}, 'source', 'connection_class'
        ),
        ConfigEntry(
            1, const.DOMAIN, 'BBB', {}, 'source', 'connection_class'
        ),
    ]

    hass.config_entries.async_entries = MagicMock(
        return_value=config_entries
    )

    config_entry = flow_handler.async_profile_config_entry

    assert not config_entry('GGGG')
    hass.config_entries.async_entries.assert_called_with(const.DOMAIN)

    assert not config_entry('CCC')
    hass.config_entries.async_entries.assert_called_with(const.DOMAIN)

    assert config_entry('Person 1') == config_entries[1]
    hass.config_entries.async_entries.assert_called_with(const.DOMAIN)


def test_flow_handler_get_auth_client(hass, flow_handler):
    """Test creation of an auth client."""
    register_flow_implementation(
        hass,
        'my_client_id',
        'my_client_secret',
        'http://localhost/',
        'Person 1'
    )

    client = flow_handler.get_auth_client('Person 1')
    assert client.client_id == 'my_client_id'
    assert client.consumer_secret == 'my_client_secret'
    assert client.callback_uri == 'http://localhost/api/withings/callback/person_1'  # pylint: disable=line-too-long  # noqa: E501
    assert client.scope == 'user.info,user.metrics,user.activity'

    # Test the base url gets path stripped and corrected.
    base_urls = [
        'https://vghome.duckdns.org/api/withings/callback/person_1',
        'https://vghome.duckdns.org/api/withings/callback/person_1/',
        'https://vghome.duckdns.org/api/withings/callback',
        'https://vghome.duckdns.org/api/withings/callback/',
    ]
    for base_url in base_urls:
        register_flow_implementation(
            hass,
            'my_client_id',
            'my_client_secret',
            base_url,
            'Person 1'
        )
        client = flow_handler.get_auth_client('Person 1')
        assert client.callback_uri == 'https://vghome.duckdns.org/api/withings/callback/person_1'  # pylint: disable=line-too-long  # noqa: E501


async def test_flow_handler_async_step_profile(flow_handler, setup_hass):
    """Test the profile step."""
    setup_hass.data[DATA_FLOW_IMPL] = {}

    result = await flow_handler.async_step_user()
    assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
    assert result['reason'] == 'no_flows'

    register_flow_implementation(
        setup_hass,
        'my_client_id',
        'my_client_secret',
        'http://localhost/',
        'Person 0'
    )
    register_flow_implementation(
        setup_hass,
        'my_client_id',
        'my_client_secret',
        'http://localhost/',
        'Person 1'
    )

    result = await flow_handler.async_step_user({
        const.PROFILE: 'Person 1',
    })
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'auth'
    assert result['description_placeholders'] == {
        'authorization_url': callee.StartsWith('https://account.withings.com/oauth2_user/authorize2?response_type=code&client_id=my_client_id&redirect_uri=http%3A%2F%2Flocalhost%2Fapi%2Fwithings%2Fcallback%2Fperson_1&scope=user.info%2Cuser.metrics%2Cuser.activity&state='),  # pylint: disable=line-too-long  # noqa: E501
        'profile': 'Person 1',
    }
    assert result['errors'] == {
        'base': 'follow_link',
    }

    result = await flow_handler.async_step_user()
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'user'
    assert result['data_schema'] is not None


async def test_flow_handler_async_step_code(flow_handler):
    """Test the code step."""
    auth_client = MagicMock(spec=nokia.NokiaAuth)
    auth_client.get_credentials = MagicMock(
        return_value=nokia.NokiaCredentials(
            access_token='my_access_token',
            token_expiry='my_token_expiry',
            token_type='my_token_type',
            refresh_token='my_refresh_token',
            user_id='my_user_id',
            client_id='my_client_id',
            consumer_secret='my_consumer_secret'
        )
    )

    get_auth_client_patch = patch.object(
        flow_handler,
        'get_auth_client',
        return_value=auth_client
    )

    with get_auth_client_patch:
        result = await flow_handler.async_step_code()
        assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
        assert result['reason'] == 'api_no_data'

        result = await flow_handler.async_step_code({})
        assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
        assert result['reason'] == 'api_no_profile_data'

        result = await flow_handler.async_step_code({
            const.PROFILE: None,
        })
        assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
        assert result['reason'] == 'api_no_profile_data'

        result = await flow_handler.async_step_code({
            const.PROFILE: 'Person 1',
        })
        assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
        assert result['reason'] == 'api_no_code_data'

        result = await flow_handler.async_step_code({
            const.PROFILE: 'Person 1',
            const.CODE: None,
        })
        assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
        assert result['reason'] == 'api_no_code_data'

        result = await flow_handler.async_step_code({
            const.PROFILE: 'Person 1',
            const.CODE: 'my_code',
        })
        assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result['title'] == 'Person 1'
        assert result['data'] == {
            const.PROFILE: 'Person 1',
            const.CREDENTIALS: {
                'access_token': 'my_access_token',
                'token_expiry': 'my_token_expiry',
                'token_type': 'my_token_type',
                'refresh_token': 'my_refresh_token',
                'user_id': 'my_user_id',
                'client_id': 'my_client_id',
                'consumer_secret': 'my_consumer_secret'
            },
        }


async def test_flow_handler_full_flow(setup_hass, flow_handler):
    """Run a test on the full config flow."""
    result = await flow_handler.async_step_user()
    assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
    assert result['reason'] == 'no_flows'

    register_flow_implementation(
        setup_hass,
        'my_client_id',
        'my_client_secret',
        'http://localhost/',
        'Person 0'
    )

    result = await flow_handler.async_step_user()
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
    assert result['step_id'] == 'user'
    assert result['data_schema'] is not None

    register_flow_implementation(
        setup_hass,
        'my_client_id',
        'my_client_secret',
        'http://localhost/',
        'Person 1'
    )

    register_view_patch = patch.object(
        setup_hass.http,
        'register_view',
        wraps=setup_hass.http.register_view
    )

    with register_view_patch as register_view:
        result = await flow_handler.async_step_auth(
            {const.PROFILE: 'Person 1'}
        )
        assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
        assert result['step_id'] == 'auth'
        assert result['description_placeholders'] == {
            'authorization_url': callee.StartsWith('https://account.withings.com/oauth2_user/authorize2?response_type=code&client_id=my_client_id&redirect_uri=http%3A%2F%2Flocalhost%2Fapi%2Fwithings%2Fcallback%2Fperson_1&scope=user.info%2Cuser.metrics%2Cuser.activity&state='),  # pylint: disable=line-too-long  # noqa: E501
            'profile': 'Person 1',
        }
        assert result['errors'] == {'base': 'follow_link'}

        callback_view = register_view.call_args[0][0]
        assert callback_view is not None
        assert callback_view.requires_auth is False
        assert callback_view.profile == 'Person 1'
        assert callback_view.url == '/api/withings/callback/person_1'
        assert callback_view.name == 'api:withings:callback:person_1'

    auth_client = MagicMock(spec=nokia.NokiaAuth)
    auth_client.get_credentials = MagicMock(
        return_value=nokia.NokiaCredentials(
            access_token='my_access_token',
            token_expiry='my_token_expiry',
            token_type='my_token_type',
            refresh_token='my_refresh_token',
            user_id='my_user_id',
            client_id='my_client_id',
            consumer_secret='my_consumer_secret'
        )
    )

    get_auth_client_patch = patch.object(
        flow_handler,
        'get_auth_client',
        return_value=auth_client
    )
    async_create_entry_patch = patch.object(
        flow_handler,
        'async_create_entry',
        wraps=flow_handler.async_create_entry
    )

    with get_auth_client_patch as get_auth_client, \
            async_create_entry_patch as async_create_entry:
        await flow_handler.async_step_code({
            const.PROFILE: 'Person 1',
            const.CODE: 'MY_CODE',
        })

        get_auth_client.assert_called_with('Person 1')
        async_create_entry.assert_called_with(
            title='Person 1',
            data={
                const.PROFILE: 'Person 1',
                const.CREDENTIALS: {
                    'access_token': 'my_access_token',
                    'token_expiry': 'my_token_expiry',
                    'token_type': 'my_token_type',
                    'refresh_token': 'my_refresh_token',
                    'user_id': 'my_user_id',
                    'client_id': 'my_client_id',
                    'consumer_secret': 'my_consumer_secret'
                },
            }
        )


def test_auth_callback_view_init():
    """Test method."""
    view = WithingsAuthCallbackView('Person 1')
    assert view.profile == 'Person 1'
    assert view.url == '/api/withings/callback/person_1'
    assert not view.requires_auth
    assert view.name == 'api:withings:callback:person_1'


def test_auth_callback_view_get(hass):
    """Test get api path."""
    view = WithingsAuthCallbackView('Person 1')
    hass.async_create_task = MagicMock(return_value=None)
    hass.config_entries.flow.async_init = MagicMock(
        return_value='AAAA'
    )

    request = MagicMock(spec=BaseRequest)
    request.app = {
        'hass': hass
    }

    assert view.get(request) == "OK!"
    hass.async_create_task.assert_not_called()
    hass.config_entries.flow.async_init.assert_not_called()

    hass.async_create_task.reset_mock()
    hass.config_entries.flow.async_init.reset_mock()

    request.query = {
        'code': 'my_code'
    }

    assert view.get(request) == "OK!"
    hass.async_create_task.assert_called_with('AAAA')
    hass.config_entries.flow.async_init.assert_called_with(
        const.DOMAIN,
        context={'source': const.CODE},
        data={
            const.PROFILE: view.profile,
            const.CODE: request.query['code'],
        },
    )
