"""The tests for the REST switch platform."""
import asyncio
from http import HTTPStatus

import aiohttp
import pytest

from homeassistant.components.rest import DOMAIN
import homeassistant.components.rest.switch as rest
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN, SwitchDeviceClass
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_HEADERS,
    CONF_NAME,
    CONF_PARAMS,
    CONF_PLATFORM,
    CONF_RESOURCE,
    CONTENT_TYPE_JSON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import assert_setup_component
from tests.test_util.aiohttp import AiohttpClientMocker

NAME = "foo"
DEVICE_CLASS = SwitchDeviceClass.SWITCH
RESOURCE = "http://localhost/"
STATE_RESOURCE = RESOURCE


async def test_setup_missing_config(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test setup with configuration missing required entries."""
    assert await async_setup_component(
        hass,
        SWITCH_DOMAIN,
        {
            SWITCH_DOMAIN: {
                CONF_PLATFORM: DOMAIN,
            }
        },
    )
    await hass.async_block_till_done()
    assert "Invalid config for [switch.rest]: required key not provided" in caplog.text


async def test_setup_missing_schema(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test setup with resource missing schema."""
    assert await async_setup_component(
        hass,
        SWITCH_DOMAIN,
        {
            SWITCH_DOMAIN: {CONF_PLATFORM: DOMAIN, CONF_RESOURCE: "localhost"},
        },
    )
    await hass.async_block_till_done()
    assert "Invalid config for [switch.rest]: invalid url" in caplog.text


async def test_setup_failed_connect(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test setup when connection error occurs."""
    aioclient_mock.get("http://localhost", exc=aiohttp.ClientError)
    assert await async_setup_component(
        hass,
        SWITCH_DOMAIN,
        {
            SWITCH_DOMAIN: {CONF_PLATFORM: DOMAIN, CONF_RESOURCE: "http://localhost"},
        },
    )
    await hass.async_block_till_done()
    assert "No route to resource/endpoint" in caplog.text


async def test_setup_timeout(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test setup when connection timeout occurs."""
    aioclient_mock.get("http://localhost", exc=asyncio.TimeoutError())
    assert await async_setup_component(
        hass,
        SWITCH_DOMAIN,
        {
            SWITCH_DOMAIN: {CONF_PLATFORM: DOMAIN, CONF_RESOURCE: "http://localhost"},
        },
    )
    await hass.async_block_till_done()
    assert "No route to resource/endpoint" in caplog.text


async def test_setup_minimum(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setup with minimum configuration."""
    aioclient_mock.get("http://localhost", status=HTTPStatus.OK)
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


async def test_setup_query_params(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setup with query params."""
    aioclient_mock.get("http://localhost/?search=something", status=HTTPStatus.OK)
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

    assert aioclient_mock.call_count == 1


async def test_setup(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Test setup with valid configuration."""
    aioclient_mock.get("http://localhost", status=HTTPStatus.OK)
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


async def test_setup_with_state_resource(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setup with valid configuration."""
    aioclient_mock.get("http://localhost", status=HTTPStatus.NOT_FOUND)
    aioclient_mock.get("http://localhost/state", status=HTTPStatus.OK)
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


async def test_setup_with_templated_headers_params(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setup with valid configuration."""
    aioclient_mock.get("http://localhost", status=HTTPStatus.OK)
    assert await async_setup_component(
        hass,
        SWITCH_DOMAIN,
        {
            SWITCH_DOMAIN: {
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
    assert_setup_component(1, SWITCH_DOMAIN)


"""Tests for REST switch platform."""


def _setup_test_switch(hass: HomeAssistant) -> None:
    headers = {"Content-type": CONTENT_TYPE_JSON}
    config = rest.PLATFORM_SCHEMA(
        {
            CONF_PLATFORM: "switch",
            CONF_NAME: NAME,
            CONF_DEVICE_CLASS: DEVICE_CLASS,
            CONF_RESOURCE: RESOURCE,
            rest.CONF_STATE_RESOURCE: STATE_RESOURCE,
            rest.CONF_HEADERS: headers,
        }
    )
    switch = rest.RestSwitch(hass, config, None)
    switch.hass = hass
    return switch, config[rest.CONF_BODY_ON], config[rest.CONF_BODY_OFF]


def test_name(hass: HomeAssistant) -> None:
    """Test the name."""
    switch, body_on, body_off = _setup_test_switch(hass)
    assert switch.name == NAME


def test_device_class(hass: HomeAssistant) -> None:
    """Test the name."""
    switch, body_on, body_off = _setup_test_switch(hass)
    assert switch.device_class == DEVICE_CLASS


def test_is_on_before_update(hass: HomeAssistant) -> None:
    """Test is_on in initial state."""
    switch, body_on, body_off = _setup_test_switch(hass)
    assert switch.is_on is None


async def test_turn_on_success(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test turn_on."""
    aioclient_mock.post(RESOURCE, status=HTTPStatus.OK)
    switch, body_on, body_off = _setup_test_switch(hass)
    await switch.async_turn_on()

    assert body_on.template == aioclient_mock.mock_calls[-1][2].decode()
    assert switch.is_on


async def test_turn_on_status_not_ok(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test turn_on when error status returned."""
    aioclient_mock.post(RESOURCE, status=HTTPStatus.INTERNAL_SERVER_ERROR)
    switch, body_on, body_off = _setup_test_switch(hass)
    await switch.async_turn_on()

    assert body_on.template == aioclient_mock.mock_calls[-1][2].decode()
    assert switch.is_on is None


async def test_turn_on_timeout(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test turn_on when timeout occurs."""
    aioclient_mock.post(RESOURCE, status=HTTPStatus.INTERNAL_SERVER_ERROR)
    switch, body_on, body_off = _setup_test_switch(hass)
    await switch.async_turn_on()

    assert switch.is_on is None


async def test_turn_off_success(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test turn_off."""
    aioclient_mock.post(RESOURCE, status=HTTPStatus.OK)
    switch, body_on, body_off = _setup_test_switch(hass)
    await switch.async_turn_off()

    assert body_off.template == aioclient_mock.mock_calls[-1][2].decode()
    assert not switch.is_on


async def test_turn_off_status_not_ok(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test turn_off when error status returned."""
    aioclient_mock.post(RESOURCE, status=HTTPStatus.INTERNAL_SERVER_ERROR)
    switch, body_on, body_off = _setup_test_switch(hass)
    await switch.async_turn_off()

    assert body_off.template == aioclient_mock.mock_calls[-1][2].decode()
    assert switch.is_on is None


async def test_turn_off_timeout(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test turn_off when timeout occurs."""
    aioclient_mock.post(RESOURCE, exc=asyncio.TimeoutError())
    switch, body_on, body_off = _setup_test_switch(hass)
    await switch.async_turn_on()

    assert switch.is_on is None


async def test_update_when_on(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test update when switch is on."""
    switch, body_on, body_off = _setup_test_switch(hass)
    aioclient_mock.get(RESOURCE, text=body_on.template)
    await switch.async_update()

    assert switch.is_on


async def test_update_when_off(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test update when switch is off."""
    switch, body_on, body_off = _setup_test_switch(hass)
    aioclient_mock.get(RESOURCE, text=body_off.template)
    await switch.async_update()

    assert not switch.is_on


async def test_update_when_unknown(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test update when unknown status returned."""
    aioclient_mock.get(RESOURCE, text="unknown status")
    switch, body_on, body_off = _setup_test_switch(hass)
    await switch.async_update()

    assert switch.is_on is None


async def test_update_timeout(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
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
        SWITCH_DOMAIN: {
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

    assert await async_setup_component(hass, SWITCH_DOMAIN, config)
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
