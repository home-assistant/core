"""The tests for the REST switch platform."""
import asyncio

import aiohttp

import homeassistant.components.rest.switch as rest
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    CONF_HEADERS,
    CONF_NAME,
    CONF_PLATFORM,
    CONF_RESOURCE,
    CONTENT_TYPE_JSON,
    HTTP_INTERNAL_SERVER_ERROR,
    HTTP_NOT_FOUND,
    HTTP_OK,
)
from homeassistant.helpers.template import Template
from homeassistant.setup import setup_component

from tests.common import assert_setup_component, get_test_home_assistant


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
        assert not asyncio.run_coroutine_threadsafe(
            rest.async_setup_platform(self.hass, {CONF_PLATFORM: rest.DOMAIN}, None),
            self.hass.loop,
        ).result()

    def test_setup_missing_schema(self):
        """Test setup with resource missing schema."""
        assert not asyncio.run_coroutine_threadsafe(
            rest.async_setup_platform(
                self.hass,
                {CONF_PLATFORM: rest.DOMAIN, CONF_RESOURCE: "localhost"},
                None,
            ),
            self.hass.loop,
        ).result()

    def test_setup_failed_connect(self, aioclient_mock):
        """Test setup when connection error occurs."""
        aioclient_mock.get("http://localhost", exc=aiohttp.ClientError)
        assert not asyncio.run_coroutine_threadsafe(
            rest.async_setup_platform(
                self.hass,
                {CONF_PLATFORM: rest.DOMAIN, CONF_RESOURCE: "http://localhost"},
                None,
            ),
            self.hass.loop,
        ).result()

    def test_setup_timeout(self, aioclient_mock):
        """Test setup when connection timeout occurs."""
        aioclient_mock.get("http://localhost", exc=asyncio.TimeoutError())
        assert not asyncio.run_coroutine_threadsafe(
            rest.async_setup_platform(
                self.hass,
                {CONF_PLATFORM: rest.DOMAIN, CONF_RESOURCE: "http://localhost"},
                None,
            ),
            self.hass.loop,
        ).result()

    def test_setup_minimum(self, aioclient_mock):
        """Test setup with minimum configuration."""
        aioclient_mock.get("http://localhost", status=HTTP_OK)
        with assert_setup_component(1, SWITCH_DOMAIN):
            assert setup_component(
                self.hass,
                SWITCH_DOMAIN,
                {
                    SWITCH_DOMAIN: {
                        CONF_PLATFORM: rest.DOMAIN,
                        CONF_RESOURCE: "http://localhost",
                    }
                },
            )
        assert aioclient_mock.call_count == 1

    def test_setup(self, aioclient_mock):
        """Test setup with valid configuration."""
        aioclient_mock.get("http://localhost", status=HTTP_OK)
        assert setup_component(
            self.hass,
            SWITCH_DOMAIN,
            {
                SWITCH_DOMAIN: {
                    CONF_PLATFORM: rest.DOMAIN,
                    CONF_NAME: "foo",
                    CONF_RESOURCE: "http://localhost",
                    CONF_HEADERS: {"Content-type": CONTENT_TYPE_JSON},
                    rest.CONF_BODY_ON: "custom on text",
                    rest.CONF_BODY_OFF: "custom off text",
                }
            },
        )
        assert aioclient_mock.call_count == 1
        assert_setup_component(1, SWITCH_DOMAIN)

    def test_setup_with_state_resource(self, aioclient_mock):
        """Test setup with valid configuration."""
        aioclient_mock.get("http://localhost", status=HTTP_NOT_FOUND)
        aioclient_mock.get("http://localhost/state", status=HTTP_OK)
        assert setup_component(
            self.hass,
            SWITCH_DOMAIN,
            {
                SWITCH_DOMAIN: {
                    CONF_PLATFORM: rest.DOMAIN,
                    CONF_NAME: "foo",
                    CONF_RESOURCE: "http://localhost",
                    rest.CONF_STATE_RESOURCE: "http://localhost/state",
                    CONF_HEADERS: {"Content-type": "application/json"},
                    rest.CONF_BODY_ON: "custom on text",
                    rest.CONF_BODY_OFF: "custom off text",
                }
            },
        )
        assert aioclient_mock.call_count == 1
        assert_setup_component(1, SWITCH_DOMAIN)


class TestRestSwitch:
    """Tests for REST switch platform."""

    def setup_method(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.name = "foo"
        self.method = "post"
        self.resource = "http://localhost/"
        self.state_resource = self.resource
        self.headers = {"Content-type": "application/json"}
        self.auth = None
        self.body_on = Template("on", self.hass)
        self.body_off = Template("off", self.hass)
        self.switch = rest.RestSwitch(
            self.name,
            self.resource,
            self.state_resource,
            self.method,
            self.headers,
            self.auth,
            self.body_on,
            self.body_off,
            None,
            10,
            True,
        )
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
        aioclient_mock.post(self.resource, status=HTTP_OK)
        asyncio.run_coroutine_threadsafe(
            self.switch.async_turn_on(), self.hass.loop
        ).result()

        assert self.body_on.template == aioclient_mock.mock_calls[-1][2].decode()
        assert self.switch.is_on

    def test_turn_on_status_not_ok(self, aioclient_mock):
        """Test turn_on when error status returned."""
        aioclient_mock.post(self.resource, status=HTTP_INTERNAL_SERVER_ERROR)
        asyncio.run_coroutine_threadsafe(
            self.switch.async_turn_on(), self.hass.loop
        ).result()

        assert self.body_on.template == aioclient_mock.mock_calls[-1][2].decode()
        assert self.switch.is_on is None

    def test_turn_on_timeout(self, aioclient_mock):
        """Test turn_on when timeout occurs."""
        aioclient_mock.post(self.resource, status=HTTP_INTERNAL_SERVER_ERROR)
        asyncio.run_coroutine_threadsafe(
            self.switch.async_turn_on(), self.hass.loop
        ).result()

        assert self.switch.is_on is None

    def test_turn_off_success(self, aioclient_mock):
        """Test turn_off."""
        aioclient_mock.post(self.resource, status=HTTP_OK)
        asyncio.run_coroutine_threadsafe(
            self.switch.async_turn_off(), self.hass.loop
        ).result()

        assert self.body_off.template == aioclient_mock.mock_calls[-1][2].decode()
        assert not self.switch.is_on

    def test_turn_off_status_not_ok(self, aioclient_mock):
        """Test turn_off when error status returned."""
        aioclient_mock.post(self.resource, status=HTTP_INTERNAL_SERVER_ERROR)
        asyncio.run_coroutine_threadsafe(
            self.switch.async_turn_off(), self.hass.loop
        ).result()

        assert self.body_off.template == aioclient_mock.mock_calls[-1][2].decode()
        assert self.switch.is_on is None

    def test_turn_off_timeout(self, aioclient_mock):
        """Test turn_off when timeout occurs."""
        aioclient_mock.post(self.resource, exc=asyncio.TimeoutError())
        asyncio.run_coroutine_threadsafe(
            self.switch.async_turn_on(), self.hass.loop
        ).result()

        assert self.switch.is_on is None

    def test_update_when_on(self, aioclient_mock):
        """Test update when switch is on."""
        aioclient_mock.get(self.resource, text=self.body_on.template)
        asyncio.run_coroutine_threadsafe(
            self.switch.async_update(), self.hass.loop
        ).result()

        assert self.switch.is_on

    def test_update_when_off(self, aioclient_mock):
        """Test update when switch is off."""
        aioclient_mock.get(self.resource, text=self.body_off.template)
        asyncio.run_coroutine_threadsafe(
            self.switch.async_update(), self.hass.loop
        ).result()

        assert not self.switch.is_on

    def test_update_when_unknown(self, aioclient_mock):
        """Test update when unknown status returned."""
        aioclient_mock.get(self.resource, text="unknown status")
        asyncio.run_coroutine_threadsafe(
            self.switch.async_update(), self.hass.loop
        ).result()

        assert self.switch.is_on is None

    def test_update_timeout(self, aioclient_mock):
        """Test update when timeout occurs."""
        aioclient_mock.get(self.resource, exc=asyncio.TimeoutError())
        asyncio.run_coroutine_threadsafe(
            self.switch.async_update(), self.hass.loop
        ).result()

        assert self.switch.is_on is None
