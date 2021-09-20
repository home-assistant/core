"""The tests for the REST switch platform."""
import asyncio

import aiohttp

from homeassistant.components.rest import DOMAIN
import homeassistant.components.rest.switch as rest
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    CONF_HEADERS,
    CONF_NAME,
    CONF_PARAMS,
    CONF_PLATFORM,
    CONF_RESOURCE,
    CONTENT_TYPE_JSON,
    HTTP_INTERNAL_SERVER_ERROR,
    HTTP_NOT_FOUND,
    HTTP_OK,
)
from homeassistant.helpers.template import Template
from homeassistant.setup import async_setup_component

from tests.common import assert_setup_component

"""Tests for setting up the REST switch platform."""

NAME = "foo"
METHOD = "post"
RESOURCE = "http://localhost/"
STATE_RESOURCE = RESOURCE
HEADERS = {"Content-type": CONTENT_TYPE_JSON}
AUTH = None
PARAMS = None


async def test_setup_missing_config(hass):
    """Test setup with configuration missing required entries."""
    assert not await rest.async_setup_platform(hass, {CONF_PLATFORM: DOMAIN}, None)


async def test_setup_missing_schema(hass):
    """Test setup with resource missing schema."""
    assert not await rest.async_setup_platform(
        hass,
        {CONF_PLATFORM: DOMAIN, CONF_RESOURCE: "localhost"},
        None,
    )


async def test_setup_failed_connect(hass, aioclient_mock):
    """Test setup when connection error occurs."""
    aioclient_mock.get("http://localhost", exc=aiohttp.ClientError)
    assert not await rest.async_setup_platform(
        hass,
        {CONF_PLATFORM: DOMAIN, CONF_RESOURCE: "http://localhost"},
        None,
    )


async def test_setup_timeout(hass, aioclient_mock):
    """Test setup when connection timeout occurs."""
    aioclient_mock.get("http://localhost", exc=asyncio.TimeoutError())
    assert not await rest.async_setup_platform(
        hass,
        {CONF_PLATFORM: DOMAIN, CONF_RESOURCE: "http://localhost"},
        None,
    )


async def test_setup_minimum(hass, aioclient_mock):
    """Test setup with minimum configuration."""
    aioclient_mock.get("http://localhost", status=HTTP_OK)
    with assert_setup_component(1, SWITCH_DOMAIN):
        assert await async_setup_component(
            hass,
            SWITCH_DOMAIN,
            {
                SWITCH_DOMAIN: {
                    CONF_PLATFORM: DOMAIN,
                    CONF_RESOURCE: "http://localhost",
                }
            },
        )
        await hass.async_block_till_done()
    assert aioclient_mock.call_count == 1


async def test_setup_query_params(hass, aioclient_mock):
    """Test setup with query params."""
    aioclient_mock.get("http://localhost/?search=something", status=HTTP_OK)
    with assert_setup_component(1, SWITCH_DOMAIN):
        assert await async_setup_component(
            hass,
            SWITCH_DOMAIN,
            {
                SWITCH_DOMAIN: {
                    CONF_PLATFORM: DOMAIN,
                    CONF_RESOURCE: "http://localhost",
                    CONF_PARAMS: {"search": "something"},
                }
            },
        )
        await hass.async_block_till_done()

    print(aioclient_mock)
    assert aioclient_mock.call_count == 1


async def test_setup(hass, aioclient_mock):
    """Test setup with valid configuration."""
    aioclient_mock.get("http://localhost", status=HTTP_OK)
    assert await async_setup_component(
        hass,
        SWITCH_DOMAIN,
        {
            SWITCH_DOMAIN: {
                CONF_PLATFORM: DOMAIN,
                CONF_NAME: "foo",
                CONF_RESOURCE: "http://localhost",
                CONF_HEADERS: {"Content-type": CONTENT_TYPE_JSON},
                rest.CONF_BODY_ON: "custom on text",
                rest.CONF_BODY_OFF: "custom off text",
            }
        },
    )
    await hass.async_block_till_done()
    assert aioclient_mock.call_count == 1
    assert_setup_component(1, SWITCH_DOMAIN)


async def test_setup_with_state_resource(hass, aioclient_mock):
    """Test setup with valid configuration."""
    aioclient_mock.get("http://localhost", status=HTTP_NOT_FOUND)
    aioclient_mock.get("http://localhost/state", status=HTTP_OK)
    assert await async_setup_component(
        hass,
        SWITCH_DOMAIN,
        {
            SWITCH_DOMAIN: {
                CONF_PLATFORM: DOMAIN,
                CONF_NAME: "foo",
                CONF_RESOURCE: "http://localhost",
                rest.CONF_STATE_RESOURCE: "http://localhost/state",
                CONF_HEADERS: {"Content-type": CONTENT_TYPE_JSON},
                rest.CONF_BODY_ON: "custom on text",
                rest.CONF_BODY_OFF: "custom off text",
            }
        },
    )
    await hass.async_block_till_done()
    assert aioclient_mock.call_count == 1
    assert_setup_component(1, SWITCH_DOMAIN)


"""Tests for REST switch platform."""


def _setup_test_switch(hass):
    body_on = Template("on", hass)
    body_off = Template("off", hass)
    switch = rest.RestSwitch(
        NAME,
        RESOURCE,
        STATE_RESOURCE,
        METHOD,
        HEADERS,
        PARAMS,
        AUTH,
        body_on,
        body_off,
        None,
        10,
        True,
    )
    switch.hass = hass
    return switch, body_on, body_off


def test_name(hass):
    """Test the name."""
    switch, body_on, body_off = _setup_test_switch(hass)
    assert switch.name == NAME


def test_is_on_before_update(hass):
    """Test is_on in initial state."""
    switch, body_on, body_off = _setup_test_switch(hass)
    assert switch.is_on is None


async def test_turn_on_success(hass, aioclient_mock):
    """Test turn_on."""
    aioclient_mock.post(RESOURCE, status=HTTP_OK)
    switch, body_on, body_off = _setup_test_switch(hass)
    await switch.async_turn_on()

    assert body_on.template == aioclient_mock.mock_calls[-1][2].decode()
    assert switch.is_on


async def test_turn_on_status_not_ok(hass, aioclient_mock):
    """Test turn_on when error status returned."""
    aioclient_mock.post(RESOURCE, status=HTTP_INTERNAL_SERVER_ERROR)
    switch, body_on, body_off = _setup_test_switch(hass)
    await switch.async_turn_on()

    assert body_on.template == aioclient_mock.mock_calls[-1][2].decode()
    assert switch.is_on is None


async def test_turn_on_timeout(hass, aioclient_mock):
    """Test turn_on when timeout occurs."""
    aioclient_mock.post(RESOURCE, status=HTTP_INTERNAL_SERVER_ERROR)
    switch, body_on, body_off = _setup_test_switch(hass)
    await switch.async_turn_on()

    assert switch.is_on is None


async def test_turn_off_success(hass, aioclient_mock):
    """Test turn_off."""
    aioclient_mock.post(RESOURCE, status=HTTP_OK)
    switch, body_on, body_off = _setup_test_switch(hass)
    await switch.async_turn_off()

    assert body_off.template == aioclient_mock.mock_calls[-1][2].decode()
    assert not switch.is_on


async def test_turn_off_status_not_ok(hass, aioclient_mock):
    """Test turn_off when error status returned."""
    aioclient_mock.post(RESOURCE, status=HTTP_INTERNAL_SERVER_ERROR)
    switch, body_on, body_off = _setup_test_switch(hass)
    await switch.async_turn_off()

    assert body_off.template == aioclient_mock.mock_calls[-1][2].decode()
    assert switch.is_on is None


async def test_turn_off_timeout(hass, aioclient_mock):
    """Test turn_off when timeout occurs."""
    aioclient_mock.post(RESOURCE, exc=asyncio.TimeoutError())
    switch, body_on, body_off = _setup_test_switch(hass)
    await switch.async_turn_on()

    assert switch.is_on is None


async def test_update_when_on(hass, aioclient_mock):
    """Test update when switch is on."""
    switch, body_on, body_off = _setup_test_switch(hass)
    aioclient_mock.get(RESOURCE, text=body_on.template)
    await switch.async_update()

    assert switch.is_on


async def test_update_when_off(hass, aioclient_mock):
    """Test update when switch is off."""
    switch, body_on, body_off = _setup_test_switch(hass)
    aioclient_mock.get(RESOURCE, text=body_off.template)
    await switch.async_update()

    assert not switch.is_on


async def test_update_when_unknown(hass, aioclient_mock):
    """Test update when unknown status returned."""
    aioclient_mock.get(RESOURCE, text="unknown status")
    switch, body_on, body_off = _setup_test_switch(hass)
    await switch.async_update()

    assert switch.is_on is None


async def test_update_timeout(hass, aioclient_mock):
    """Test update when timeout occurs."""
    aioclient_mock.get(RESOURCE, exc=asyncio.TimeoutError())
    switch, body_on, body_off = _setup_test_switch(hass)
    await switch.async_update()

    assert switch.is_on is None
