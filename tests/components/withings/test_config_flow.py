"""Tests for the Withings config flow."""
import nokia
import callee
from asynctest import patch, MagicMock
from aiohttp.web_request import BaseRequest
from homeassistant.config_entries import ConfigEntry
from homeassistant import data_entry_flow, setup
from tests.common import get_test_home_assistant
from homeassistant.components.withings.config_flow import (
    register_flow_implementation,
    WithingsFlowHandler,
    WithingsAuthCallbackView,
    DATA_FLOW_IMPL
)
from homeassistant.components.withings import (
    const
)
import homeassistant.components.http as http
import homeassistant.components.api as api


class TestWithingsFlowHandler:
    """Test class for the withings flow handler."""

    def setup_method(self):
        """Set up the flow handler."""
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

        self.hass = get_test_home_assistant()
        self.flow_handler = WithingsFlowHandler()
        self.flow_handler.hass = self.hass
        self.hass.data = {}

        setup.setup_component(self.hass, 'http', config)
        setup.setup_component(self.hass, 'api', config)

    def teardown_method(self):
        """Tear down the test."""
        self.hass.stop()

    def test_init(self):
        """Test the init of the flow handler."""
        assert not self.flow_handler.flow_profile

    def test_async_profile_config_entry(self):
        """Test profile config entry."""
        config_entries = [
            ConfigEntry(
                '1', const.DOMAIN, 'AAA', {}, 'source', 'connection_class'
            ),
            ConfigEntry(
                '1', const.DOMAIN, 'Person 1', {}, 'source', 'connection_class'
            ),
            ConfigEntry(
                '1', const.DOMAIN, 'BBB', {}, 'source', 'connection_class'
            ),
        ]

        self.hass.config_entries.async_entries = MagicMock(
            return_value=config_entries
        )

        config_entry = self.flow_handler.async_profile_config_entry

        assert not config_entry('GGGG')
        self.hass.config_entries.async_entries.assert_called_with(const.DOMAIN)

        assert not config_entry('CCC')
        self.hass.config_entries.async_entries.assert_called_with(const.DOMAIN)

        assert config_entry('Person 1') == config_entries[1]
        self.hass.config_entries.async_entries.assert_called_with(const.DOMAIN)

    def test_get_auth_client(self):
        """Test creation of an auth client."""
        register_flow_implementation(
            self.hass,
            'my_client_id',
            'my_client_secret',
            'http://localhost/',
            'Person 1'
        )

        client = self.flow_handler.get_auth_client('Person 1')
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
                self.hass,
                'my_client_id',
                'my_client_secret',
                base_url,
                'Person 1'
            )
            client = self.flow_handler.get_auth_client('Person 1')
            assert client.callback_uri == 'https://vghome.duckdns.org/api/withings/callback/person_1'  # pylint: disable=line-too-long  # noqa: E501

    async def test_async_step_profile(self):
        """Test the profile step."""
        self.hass.data[DATA_FLOW_IMPL] = {}

        result = await self.flow_handler.async_step_user()
        assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
        assert result['reason'] == 'no_flows'

        register_flow_implementation(
            self.hass,
            'my_client_id',
            'my_client_secret',
            'http://localhost/',
            'Person 0'
        )
        register_flow_implementation(
            self.hass,
            'my_client_id',
            'my_client_secret',
            'http://localhost/',
            'Person 1'
        )

        result = await self.flow_handler.async_step_user({
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

        result = await self.flow_handler.async_step_user()
        assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
        assert result['step_id'] == 'user'
        assert result['data_schema'] is not None

    async def test_async_step_code(self):
        """Test the code step."""
        auth_client = MagicMock(spec=nokia.NokiaAuth)
        auth_client.get_credentials = MagicMock(return_value=nokia.NokiaCredentials(
            access_token='my_access_token',
            token_expiry='my_token_expiry',
            token_type='my_token_type',
            refresh_token='my_refresh_token',
            user_id='my_user_id',
            client_id='my_client_id',
            consumer_secret='my_consumer_secret'
        ))

        get_auth_client_patch = patch.object(
            self.flow_handler,
            'get_auth_client',
            return_value=auth_client
        )

        with get_auth_client_patch:
            result = await self.flow_handler.async_step_code()
            assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
            assert result['reason'] == 'api_no_data'

            result = await self.flow_handler.async_step_code({})
            assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
            assert result['reason'] == 'api_no_profile_data'

            result = await self.flow_handler.async_step_code({
                const.PROFILE: None,
            })
            assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
            assert result['reason'] == 'api_no_profile_data'

            result = await self.flow_handler.async_step_code({
                const.PROFILE: 'Person 1',
            })
            assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
            assert result['reason'] == 'api_no_code_data'

            result = await self.flow_handler.async_step_code({
                const.PROFILE: 'Person 1',
                const.CODE: None,
            })
            assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
            assert result['reason'] == 'api_no_code_data'

            result = await self.flow_handler.async_step_code({
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

    async def test_full_flow(self):
        """Run a test on the full config flow."""
        result = await self.flow_handler.async_step_user()
        assert result['type'] == data_entry_flow.RESULT_TYPE_ABORT
        assert result['reason'] == 'no_flows'

        register_flow_implementation(
            self.hass,
            'my_client_id',
            'my_client_secret',
            'http://localhost/',
            'Person 0'
        )

        result = await self.flow_handler.async_step_user()
        assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
        assert result['step_id'] == 'user'
        assert result['data_schema'] is not None

        register_flow_implementation(
            self.hass,
            'my_client_id',
            'my_client_secret',
            'http://localhost/',
            'Person 1'
        )

        register_view_patch = patch.object(
            self.hass.http,
            'register_view',
            wraps=self.hass.http.register_view
        )

        with register_view_patch as register_view:
            result = await self.flow_handler.async_step_auth(
                {const.PROFILE: 'Person 1'}
            )
            assert result['type'] == data_entry_flow.RESULT_TYPE_FORM
            assert result['step_id'] == 'auth'
            assert result['description_placeholders'] == {
                'authorization_url': callee.StartsWith('https://account.withings.com/oauth2_user/authorize2?response_type=code&client_id=my_client_id&redirect_uri=http%3A%2F%2Flocalhost%2Fapi%2Fwithings%2Fcallback%2Fperson_1&scope=user.info%2Cuser.metrics%2Cuser.activity&state='),  # pylint: disable=line-too-long  # noqa: E501
                'profile': 'Person 1',
            }
            assert result['errors'] == {'base': 'follow_link'}

            callback_view: WithingsAuthCallbackView = \
                register_view.call_args[0][0]
            assert callback_view is not None
            assert callback_view.requires_auth is False
            assert callback_view.profile == 'Person 1'
            assert callback_view.url == '/api/withings/callback/person_1'
            assert callback_view.name == 'api:withings:callback:person_1'

        auth_client = MagicMock(spec=nokia.NokiaAuth)
        auth_client.get_credentials = MagicMock(return_value=nokia.NokiaCredentials(
            access_token='my_access_token',
            token_expiry='my_token_expiry',
            token_type='my_token_type',
            refresh_token='my_refresh_token',
            user_id='my_user_id',
            client_id='my_client_id',
            consumer_secret='my_consumer_secret'
        ))

        get_auth_client_patch = patch.object(
            self.flow_handler,
            'get_auth_client',
            return_value=auth_client
        )
        async_create_entry_patch = patch.object(
            self.flow_handler,
            'async_create_entry',
            wraps=self.flow_handler.async_create_entry
        )

        with get_auth_client_patch as get_auth_client, \
                async_create_entry_patch as async_create_entry:
            await self.flow_handler.async_step_code({
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


class TestWithingsAuthCallbackView:
    """Tests the auth callback view."""

    def setup_method(self):
        """Set up the test."""
        self.hass = get_test_home_assistant()

    def teardown_method(self):
        """Tear down the test."""
        self.hass.stop()

    @staticmethod
    def test_init():
        """Test method."""
        view = WithingsAuthCallbackView('Person 1')
        assert view.profile == 'Person 1'
        assert view.url == '/api/withings/callback/person_1'
        assert not view.requires_auth
        assert view.name == 'api:withings:callback:person_1'

    def test_get(self):
        """Test get api path."""
        view = WithingsAuthCallbackView('Person 1')
        self.hass.async_create_task = MagicMock(return_value=None)
        self.hass.config_entries.flow.async_init = MagicMock(
            return_value='AAAA'
        )

        request = MagicMock(spec=BaseRequest)
        request.app = {
            'hass': self.hass
        }

        assert view.get(request) == "OK!"
        self.hass.async_create_task.assert_not_called()
        self.hass.config_entries.flow.async_init.assert_not_called()

        self.hass.async_create_task.reset_mock()
        self.hass.config_entries.flow.async_init.reset_mock()

        request.query = {
            'code': 'my_code'
        }

        assert view.get(request) == "OK!"
        self.hass.async_create_task.assert_called_with('AAAA')
        self.hass.config_entries.flow.async_init.assert_called_with(
            const.DOMAIN,
            context={'source': const.CODE},
            data={
                const.PROFILE: view.profile,
                const.CODE: request.query['code'],
            },
        )
