"""The tests for the REST switch platform."""
import asyncio
from http import HTTPStatus

import aiohttp

from homeassistant.components.rest import DOMAIN
import homeassistant.components.rest.switch as rest
from homeassistant.components.switch import SwitchDeviceClass
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_HEADERS,
    CONF_NAME,
    CONF_PARAMS,
    CONF_PLATFORM,
    CONF_RESOURCE,
    CONTENT_TYPE_JSON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.template import Template
from homeassistant.setup import async_setup_component

from tests.common import assert_setup_component
from tests.test_util.aiohttp import AiohttpClientMocker

NAME = "foo"
DEVICE_CLASS = SwitchDeviceClass.SWITCH
METHOD = "post"
RESOURCE = "http://localhost/"
STATE_RESOURCE = RESOURCE
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
    aioclient_mock.get("http://localhost", status=HTTPStatus.OK)
    with assert_setup_component(1, Platform.SWITCH):
        assert await async_setup_component(
            hass,
            Platform.SWITCH,
            {
                Platform.SWITCH: {
                    CONF_PLATFORM: DOMAIN,
                    CONF_RESOURCE: "http://localhost",
                }
            },
        )
        await hass.async_block_till_done()
    assert aioclient_mock.call_count == 1


async def test_setup_query_params(hass, aioclient_mock):
    """Test setup with query params."""
    aioclient_mock.get("http://localhost/?search=something", status=HTTPStatus.OK)
    with assert_setup_component(1, Platform.SWITCH):
        assert await async_setup_component(
            hass,
            Platform.SWITCH,
            {
                Platform.SWITCH: {
                    CONF_PLATFORM: DOMAIN,
                    CONF_RESOURCE: "http://localhost",
                    CONF_PARAMS: {"search": "something"},
                }
            },
        )
        await hass.async_block_till_done()

    assert aioclient_mock.call_count == 1


async def test_setup(hass, aioclient_mock):
    """Test setup with valid configuration."""
    aioclient_mock.get("http://localhost", status=HTTPStatus.OK)
    assert await async_setup_component(
        hass,
        Platform.SWITCH,
        {
            Platform.SWITCH: {
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
    assert_setup_component(1, Platform.SWITCH)


async def test_setup_with_state_resource(hass, aioclient_mock):
    """Test setup with valid configuration."""
    aioclient_mock.get("http://localhost", status=HTTPStatus.NOT_FOUND)
    aioclient_mock.get("http://localhost/state", status=HTTPStatus.OK)
    assert await async_setup_component(
        hass,
        Platform.SWITCH,
        {
            Platform.SWITCH: {
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
    assert_setup_component(1, Platform.SWITCH)


async def test_setup_with_templated_headers_params(hass, aioclient_mock):
    """Test setup with valid configuration."""
    aioclient_mock.get("http://localhost", status=HTTPStatus.OK)
    assert await async_setup_component(
        hass,
        Platform.SWITCH,
        {
            Platform.SWITCH: {
                CONF_PLATFORM: DOMAIN,
                CONF_NAME: "foo",
                CONF_RESOURCE: "http://localhost",
                CONF_HEADERS: {
                    "Accept": CONTENT_TYPE_JSON,
                    "User-Agent": "Mozilla/{{ 3 + 2 }}.0",
                },
                CONF_PARAMS: {
                    "start": 0,
                    "end": "{{ 3 + 2 }}",
                },
            }
        },
    )
    await hass.async_block_till_done()
    assert aioclient_mock.call_count == 1
    assert aioclient_mock.mock_calls[-1][3].get("Accept") == CONTENT_TYPE_JSON
    assert aioclient_mock.mock_calls[-1][3].get("User-Agent") == "Mozilla/5.0"
    assert aioclient_mock.mock_calls[-1][1].query["start"] == "0"
    assert aioclient_mock.mock_calls[-1][1].query["end"] == "5"
    assert_setup_component(1, Platform.SWITCH)


"""Tests for REST switch platform."""


def _setup_test_switch(hass):
    body_on = Template("on", hass)
    body_off = Template("off", hass)
    headers = {"Content-type": Template(CONTENT_TYPE_JSON, hass)}
    switch = rest.RestSwitch(
        hass,
        {
            CONF_NAME: Template(NAME, hass),
            CONF_DEVICE_CLASS: DEVICE_CLASS,
            CONF_RESOURCE: RESOURCE,
            rest.CONF_STATE_RESOURCE: STATE_RESOURCE,
            rest.CONF_METHOD: METHOD,
            rest.CONF_HEADERS: headers,
            rest.CONF_PARAMS: PARAMS,
            rest.CONF_BODY_ON: body_on,
            rest.CONF_BODY_OFF: body_off,
            rest.CONF_IS_ON_TEMPLATE: None,
            rest.CONF_TIMEOUT: 10,
            rest.CONF_VERIFY_SSL: True,
        },
        None,
    )
    switch.hass = hass
    return switch, body_on, body_off


def test_name(hass):
    """Test the name."""
    switch, body_on, body_off = _setup_test_switch(hass)
    assert switch.name == NAME


def test_device_class(hass):
    """Test the name."""
    switch, body_on, body_off = _setup_test_switch(hass)
    assert switch.device_class == DEVICE_CLASS


def test_is_on_before_update(hass):
    """Test is_on in initial state."""
    switch, body_on, body_off = _setup_test_switch(hass)
    assert switch.is_on is None


async def test_turn_on_success(hass, aioclient_mock):
    """Test turn_on."""
    aioclient_mock.post(RESOURCE, status=HTTPStatus.OK)
    switch, body_on, body_off = _setup_test_switch(hass)
    await switch.async_turn_on()

    assert body_on.template == aioclient_mock.mock_calls[-1][2].decode()
    assert switch.is_on


async def test_turn_on_status_not_ok(hass, aioclient_mock):
    """Test turn_on when error status returned."""
    aioclient_mock.post(RESOURCE, status=HTTPStatus.INTERNAL_SERVER_ERROR)
    switch, body_on, body_off = _setup_test_switch(hass)
    await switch.async_turn_on()

    assert body_on.template == aioclient_mock.mock_calls[-1][2].decode()
    assert switch.is_on is None


async def test_turn_on_timeout(hass, aioclient_mock):
    """Test turn_on when timeout occurs."""
    aioclient_mock.post(RESOURCE, status=HTTPStatus.INTERNAL_SERVER_ERROR)
    switch, body_on, body_off = _setup_test_switch(hass)
    await switch.async_turn_on()

    assert switch.is_on is None


async def test_turn_off_success(hass, aioclient_mock):
    """Test turn_off."""
    aioclient_mock.post(RESOURCE, status=HTTPStatus.OK)
    switch, body_on, body_off = _setup_test_switch(hass)
    await switch.async_turn_off()

    assert body_off.template == aioclient_mock.mock_calls[-1][2].decode()
    assert not switch.is_on


async def test_turn_off_status_not_ok(hass, aioclient_mock):
    """Test turn_off when error status returned."""
    aioclient_mock.post(RESOURCE, status=HTTPStatus.INTERNAL_SERVER_ERROR)
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


async def test_entity_config(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test entity configuration."""

    aioclient_mock.get("http://localhost", status=HTTPStatus.OK)
    config = {
        Platform.SWITCH: {
            # REST configuration
            "platform": "rest",
            "method": "POST",
            "resource": "http://localhost",
            # Entity configuration
            "icon": "{{'mdi:one_two_three'}}",
            "picture": "{{'blabla.png'}}",
            "name": "{{'REST' + ' ' + 'Switch'}}",
            "unique_id": "very_unique",
        },
    }

    assert await async_setup_component(hass, Platform.SWITCH, config)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    assert entity_registry.async_get("switch.rest_switch").unique_id == "very_unique"

    state = hass.states.get("switch.rest_switch")
    assert state.state == "unknown"
    assert state.attributes == {
        "entity_picture": "blabla.png",
        "friendly_name": "REST Switch",
        "icon": "mdi:one_two_three",
    }
