"""The tests for the REST switch platform."""
import asyncio

import aiohttp

import homeassistant.components.rest.switch as rest
from homeassistant.setup import setup_component
from homeassistant.util.async_ import run_coroutine_threadsafe
from homeassistant.helpers.template import Template
from tests.common import get_test_home_assistant, assert_setup_component


class TestRestSwitchSetup:
    """Tests for setting up the REST switch platform."""

    def setup_method(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def teardown_method(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_setup_missing_config(self):
        """Test setup with configuration missing required entries."""
        assert not run_coroutine_threadsafe(
            rest.async_setup_platform(self.hass, {
                'platform': 'rest'
            }, None),
            self.hass.loop
        ).result()

    def test_setup_missing_schema(self):
        """Test setup with resource missing schema."""
        assert not run_coroutine_threadsafe(
            rest.async_setup_platform(self.hass, {
                'platform': 'rest',
                'resource': 'localhost'
            }, None),
            self.hass.loop
        ).result()

    def test_setup_failed_connect(self, aioclient_mock):
        """Test setup when connection error occurs."""
        aioclient_mock.get('http://localhost', exc=aiohttp.ClientError)
        assert not run_coroutine_threadsafe(
            rest.async_setup_platform(self.hass, {
                'platform': 'rest',
                'resource': 'http://localhost',
            }, None),
            self.hass.loop
        ).result()

    def test_setup_timeout(self, aioclient_mock):
        """Test setup when connection timeout occurs."""
        aioclient_mock.get('http://localhost', exc=asyncio.TimeoutError())
        assert not run_coroutine_threadsafe(
            rest.async_setup_platform(self.hass, {
                'platform': 'rest',
                'resource': 'http://localhost',
            }, None),
            self.hass.loop
        ).result()

    def test_setup_minimum(self, aioclient_mock):
        """Test setup with minimum configuration."""
        aioclient_mock.get('http://localhost', status=200)
        with assert_setup_component(1, 'switch'):
            assert setup_component(self.hass, 'switch', {
                'switch': {
                    'platform': 'rest',
                    'resource': 'http://localhost'
                }
            })
        assert aioclient_mock.call_count == 1

    def test_setup(self, aioclient_mock):
        """Test setup with valid configuration."""
        aioclient_mock.get('http://localhost', status=200)
        assert setup_component(self.hass, 'switch', {
            'switch': {
                'platform': 'rest',
                'name': 'foo',
                'resource': 'http://localhost',
                'headers': {'Content-type': 'application/json'},
                'body_on': 'custom on text',
                'body_off': 'custom off text',
            }
        })
        assert aioclient_mock.call_count == 1
        assert_setup_component(1, 'switch')


class TestRestSwitch:
    """Tests for REST switch platform."""

    def setup_method(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.name = 'foo'
        self.method = 'post'
        self.resource = 'http://localhost/'
        self.headers = {'Content-type': 'application/json'}
        self.auth = None
        self.body_on = Template('on', self.hass)
        self.body_off = Template('off', self.hass)
        self.switch = rest.RestSwitch(
            self.name, self.resource, self.method, self.headers, self.auth,
            self.body_on, self.body_off, None, 10, True)
        self.switch.hass = self.hass

    def teardown_method(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_name(self):
        """Test the name."""
        assert self.name == self.switch.name

    def test_is_on_before_update(self):
        """Test is_on in initial state."""
        assert self.switch.is_on is None

    def test_turn_on_success(self, aioclient_mock):
        """Test turn_on."""
        aioclient_mock.post(self.resource, status=200)
        run_coroutine_threadsafe(
            self.switch.async_turn_on(), self.hass.loop).result()

        assert self.body_on.template == \
            aioclient_mock.mock_calls[-1][2].decode()
        assert self.switch.is_on

    def test_turn_on_status_not_ok(self, aioclient_mock):
        """Test turn_on when error status returned."""
        aioclient_mock.post(self.resource, status=500)
        run_coroutine_threadsafe(
            self.switch.async_turn_on(), self.hass.loop).result()

        assert self.body_on.template == \
            aioclient_mock.mock_calls[-1][2].decode()
        assert self.switch.is_on is None

    def test_turn_on_timeout(self, aioclient_mock):
        """Test turn_on when timeout occurs."""
        aioclient_mock.post(self.resource, status=500)
        run_coroutine_threadsafe(
            self.switch.async_turn_on(), self.hass.loop).result()

        assert self.switch.is_on is None

    def test_turn_off_success(self, aioclient_mock):
        """Test turn_off."""
        aioclient_mock.post(self.resource, status=200)
        run_coroutine_threadsafe(
            self.switch.async_turn_off(), self.hass.loop).result()

        assert self.body_off.template == \
            aioclient_mock.mock_calls[-1][2].decode()
        assert not self.switch.is_on

    def test_turn_off_status_not_ok(self, aioclient_mock):
        """Test turn_off when error status returned."""
        aioclient_mock.post(self.resource, status=500)
        run_coroutine_threadsafe(
            self.switch.async_turn_off(), self.hass.loop).result()

        assert self.body_off.template == \
            aioclient_mock.mock_calls[-1][2].decode()
        assert self.switch.is_on is None

    def test_turn_off_timeout(self, aioclient_mock):
        """Test turn_off when timeout occurs."""
        aioclient_mock.post(self.resource, exc=asyncio.TimeoutError())
        run_coroutine_threadsafe(
            self.switch.async_turn_on(), self.hass.loop).result()

        assert self.switch.is_on is None

    def test_update_when_on(self, aioclient_mock):
        """Test update when switch is on."""
        aioclient_mock.get(self.resource, text=self.body_on.template)
        run_coroutine_threadsafe(
            self.switch.async_update(), self.hass.loop).result()

        assert self.switch.is_on

    def test_update_when_off(self, aioclient_mock):
        """Test update when switch is off."""
        aioclient_mock.get(self.resource, text=self.body_off.template)
        run_coroutine_threadsafe(
            self.switch.async_update(), self.hass.loop).result()

        assert not self.switch.is_on

    def test_update_when_unknown(self, aioclient_mock):
        """Test update when unknown status returned."""
        aioclient_mock.get(self.resource, text='unknown status')
        run_coroutine_threadsafe(
            self.switch.async_update(), self.hass.loop).result()

        assert self.switch.is_on is None

    def test_update_timeout(self, aioclient_mock):
        """Test update when timeout occurs."""
        aioclient_mock.get(self.resource, exc=asyncio.TimeoutError())
        run_coroutine_threadsafe(
            self.switch.async_update(), self.hass.loop).result()

        assert self.switch.is_on is None
