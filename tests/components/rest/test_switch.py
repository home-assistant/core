"""The tests for the REST switch platform."""
import asyncio
from http import HTTPStatus

import aiohttp
import pytest

from homeassistant.components.rest import DOMAIN
from homeassistant.components.rest.switch import (
    CONF_BODY_OFF,
    CONF_BODY_ON,
    CONF_STATE_RESOURCE,
)
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SCAN_INTERVAL,
    SwitchDeviceClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_ENTITY_PICTURE,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    CONF_DEVICE_CLASS,
    CONF_HEADERS,
    CONF_ICON,
    CONF_METHOD,
    CONF_NAME,
    CONF_PARAMS,
    CONF_PLATFORM,
    CONF_RESOURCE,
    CONF_UNIQUE_ID,
    CONTENT_TYPE_JSON,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.template_entity import CONF_PICTURE
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from tests.common import assert_setup_component, async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker

NAME = "foo"
DEVICE_CLASS = SwitchDeviceClass.SWITCH
RESOURCE = "http://localhost/"
STATE_RESOURCE = RESOURCE


async def test_setup_missing_config(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test setup with configuration missing required entries."""
    config = {SWITCH_DOMAIN: {CONF_PLATFORM: DOMAIN}}
    assert await async_setup_component(hass, SWITCH_DOMAIN, config)
    await hass.async_block_till_done()
    assert_setup_component(0, SWITCH_DOMAIN)
    assert "Invalid config for [switch.rest]: required key not provided" in caplog.text


async def test_setup_missing_schema(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test setup with resource missing schema."""
    config = {SWITCH_DOMAIN: {CONF_PLATFORM: DOMAIN, CONF_RESOURCE: "localhost"}}
    assert await async_setup_component(hass, SWITCH_DOMAIN, config)
    await hass.async_block_till_done()
    assert_setup_component(0, SWITCH_DOMAIN)
    assert "Invalid config for [switch.rest]: invalid url" in caplog.text


async def test_setup_failed_connect(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test setup when connection error occurs."""
    aioclient_mock.get(RESOURCE, exc=aiohttp.ClientError)
    config = {SWITCH_DOMAIN: {CONF_PLATFORM: DOMAIN, CONF_RESOURCE: RESOURCE}}
    assert await async_setup_component(hass, SWITCH_DOMAIN, config)
    await hass.async_block_till_done()
    assert_setup_component(0, SWITCH_DOMAIN)
    assert "No route to resource/endpoint" in caplog.text


async def test_setup_timeout(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test setup when connection timeout occurs."""
    aioclient_mock.get(RESOURCE, exc=asyncio.TimeoutError())
    config = {SWITCH_DOMAIN: {CONF_PLATFORM: DOMAIN, CONF_RESOURCE: RESOURCE}}
    assert await async_setup_component(hass, SWITCH_DOMAIN, config)
    await hass.async_block_till_done()
    assert_setup_component(0, SWITCH_DOMAIN)
    assert "No route to resource/endpoint" in caplog.text


async def test_setup_minimum(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setup with minimum configuration."""
    aioclient_mock.get(RESOURCE, status=HTTPStatus.OK)
    config = {SWITCH_DOMAIN: {CONF_PLATFORM: DOMAIN, CONF_RESOURCE: RESOURCE}}
    with assert_setup_component(1, SWITCH_DOMAIN):
        assert await async_setup_component(hass, SWITCH_DOMAIN, config)
        await hass.async_block_till_done()
    assert aioclient_mock.call_count == 1


async def test_setup_query_params(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setup with query params."""
    aioclient_mock.get("http://localhost/?search=something", status=HTTPStatus.OK)
    config = {
        SWITCH_DOMAIN: {
            CONF_PLATFORM: DOMAIN,
            CONF_RESOURCE: RESOURCE,
            CONF_PARAMS: {"search": "something"},
        }
    }
    with assert_setup_component(1, SWITCH_DOMAIN):
        assert await async_setup_component(hass, SWITCH_DOMAIN, config)
        await hass.async_block_till_done()

    assert aioclient_mock.call_count == 1


async def test_setup(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Test setup with valid configuration."""
    aioclient_mock.get(RESOURCE, status=HTTPStatus.OK)
    config = {
        SWITCH_DOMAIN: {
            CONF_PLATFORM: DOMAIN,
            CONF_NAME: "foo",
            CONF_RESOURCE: RESOURCE,
            CONF_HEADERS: {"Content-type": CONTENT_TYPE_JSON},
            CONF_BODY_ON: "custom on text",
            CONF_BODY_OFF: "custom off text",
        }
    }
    assert await async_setup_component(hass, SWITCH_DOMAIN, config)
    await hass.async_block_till_done()
    assert aioclient_mock.call_count == 1
    assert_setup_component(1, SWITCH_DOMAIN)


async def test_setup_with_state_resource(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setup with valid configuration."""
    aioclient_mock.get(RESOURCE, status=HTTPStatus.NOT_FOUND)
    aioclient_mock.get("http://localhost/state", status=HTTPStatus.OK)
    config = {
        SWITCH_DOMAIN: {
            CONF_PLATFORM: DOMAIN,
            CONF_NAME: "foo",
            CONF_RESOURCE: RESOURCE,
            CONF_STATE_RESOURCE: "http://localhost/state",
            CONF_HEADERS: {"Content-type": CONTENT_TYPE_JSON},
            CONF_BODY_ON: "custom on text",
            CONF_BODY_OFF: "custom off text",
        }
    }
    assert await async_setup_component(hass, SWITCH_DOMAIN, config)
    await hass.async_block_till_done()
    assert aioclient_mock.call_count == 1
    assert_setup_component(1, SWITCH_DOMAIN)


async def test_setup_with_templated_headers_params(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test setup with valid configuration."""
    aioclient_mock.get(RESOURCE, status=HTTPStatus.OK)
    config = {
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
    }
    assert await async_setup_component(hass, SWITCH_DOMAIN, config)
    await hass.async_block_till_done()
    assert aioclient_mock.call_count == 1
    assert aioclient_mock.mock_calls[-1][3].get("Accept") == CONTENT_TYPE_JSON
    assert aioclient_mock.mock_calls[-1][3].get("User-Agent") == "Mozilla/5.0"
    assert aioclient_mock.mock_calls[-1][1].query["start"] == "0"
    assert aioclient_mock.mock_calls[-1][1].query["end"] == "5"
    assert_setup_component(1, SWITCH_DOMAIN)


# Tests for REST switch platform.


async def _async_setup_test_switch(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(RESOURCE, status=HTTPStatus.OK)

    headers = {"Content-type": CONTENT_TYPE_JSON}
    config = {
        CONF_PLATFORM: DOMAIN,
        CONF_NAME: NAME,
        CONF_DEVICE_CLASS: DEVICE_CLASS,
        CONF_RESOURCE: RESOURCE,
        CONF_STATE_RESOURCE: STATE_RESOURCE,
        CONF_HEADERS: headers,
    }

    assert await async_setup_component(hass, SWITCH_DOMAIN, {SWITCH_DOMAIN: config})
    await hass.async_block_till_done()
    assert_setup_component(1, SWITCH_DOMAIN)

    assert hass.states.get("switch.foo").state == STATE_UNKNOWN
    aioclient_mock.clear_requests()


async def test_name(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Test the name."""
    await _async_setup_test_switch(hass, aioclient_mock)

    state = hass.states.get("switch.foo")
    assert state.attributes[ATTR_FRIENDLY_NAME] == NAME


async def test_device_class(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the device class."""
    await _async_setup_test_switch(hass, aioclient_mock)

    state = hass.states.get("switch.foo")
    assert state.attributes[ATTR_DEVICE_CLASS] == DEVICE_CLASS


async def test_is_on_before_update(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test is_on in initial state."""
    await _async_setup_test_switch(hass, aioclient_mock)

    state = hass.states.get("switch.foo")
    assert state.state == STATE_UNKNOWN


async def test_turn_on_success(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test turn_on."""
    await _async_setup_test_switch(hass, aioclient_mock)

    aioclient_mock.post(RESOURCE, status=HTTPStatus.OK)
    aioclient_mock.get(RESOURCE, exc=aiohttp.ClientError)
    assert await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.foo"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert aioclient_mock.mock_calls[-2][2].decode() == "ON"
    assert hass.states.get("switch.foo").state == STATE_ON


async def test_turn_on_status_not_ok(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test turn_on when error status returned."""
    await _async_setup_test_switch(hass, aioclient_mock)

    aioclient_mock.post(RESOURCE, status=HTTPStatus.INTERNAL_SERVER_ERROR)
    assert await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.foo"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert aioclient_mock.mock_calls[-1][2].decode() == "ON"
    assert hass.states.get("switch.foo").state == STATE_UNKNOWN


async def test_turn_on_timeout(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test turn_on when timeout occurs."""
    await _async_setup_test_switch(hass, aioclient_mock)

    aioclient_mock.post(RESOURCE, status=HTTPStatus.INTERNAL_SERVER_ERROR)
    assert await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.foo"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.get("switch.foo").state == STATE_UNKNOWN


async def test_turn_off_success(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test turn_off."""
    await _async_setup_test_switch(hass, aioclient_mock)

    aioclient_mock.post(RESOURCE, status=HTTPStatus.OK)
    aioclient_mock.get(RESOURCE, exc=aiohttp.ClientError)
    assert await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.foo"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert aioclient_mock.mock_calls[-2][2].decode() == "OFF"

    assert hass.states.get("switch.foo").state == STATE_OFF


async def test_turn_off_status_not_ok(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test turn_off when error status returned."""
    await _async_setup_test_switch(hass, aioclient_mock)

    aioclient_mock.post(RESOURCE, status=HTTPStatus.INTERNAL_SERVER_ERROR)
    assert await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.foo"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert aioclient_mock.mock_calls[-1][2].decode() == "OFF"

    assert hass.states.get("switch.foo").state == STATE_UNKNOWN


async def test_turn_off_timeout(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test turn_off when timeout occurs."""
    await _async_setup_test_switch(hass, aioclient_mock)

    aioclient_mock.post(RESOURCE, exc=asyncio.TimeoutError())
    assert await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.foo"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.get("switch.foo").state == STATE_UNKNOWN


async def test_update_when_on(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test update when switch is on."""
    await _async_setup_test_switch(hass, aioclient_mock)

    aioclient_mock.get(RESOURCE, text="ON")
    async_fire_time_changed(hass, utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()

    assert hass.states.get("switch.foo").state == STATE_ON


async def test_update_when_off(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test update when switch is off."""
    await _async_setup_test_switch(hass, aioclient_mock)

    aioclient_mock.get(RESOURCE, text="OFF")
    async_fire_time_changed(hass, utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()

    assert hass.states.get("switch.foo").state == STATE_OFF


async def test_update_when_unknown(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test update when unknown status returned."""
    await _async_setup_test_switch(hass, aioclient_mock)

    aioclient_mock.get(RESOURCE, text="unknown status")
    async_fire_time_changed(hass, utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()

    assert hass.states.get("switch.foo").state == STATE_UNKNOWN


async def test_update_timeout(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test update when timeout occurs."""
    await _async_setup_test_switch(hass, aioclient_mock)

    aioclient_mock.get(RESOURCE, exc=asyncio.TimeoutError())
    async_fire_time_changed(hass, utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()

    assert hass.states.get("switch.foo").state == STATE_UNKNOWN


async def test_entity_config(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test entity configuration."""

    aioclient_mock.get(RESOURCE, status=HTTPStatus.OK)
    config = {
        SWITCH_DOMAIN: {
            # REST configuration
            CONF_PLATFORM: "rest",
            CONF_METHOD: "POST",
            CONF_RESOURCE: "http://localhost",
            # Entity configuration
            CONF_ICON: "{{'mdi:one_two_three'}}",
            CONF_PICTURE: "{{'blabla.png'}}",
            CONF_NAME: "{{'REST' + ' ' + 'Switch'}}",
            CONF_UNIQUE_ID: "very_unique",
        },
    }

    assert await async_setup_component(hass, SWITCH_DOMAIN, config)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    assert entity_registry.async_get("switch.rest_switch").unique_id == "very_unique"

    state = hass.states.get("switch.rest_switch")
    assert state.state == "unknown"
    assert state.attributes == {
        ATTR_ENTITY_PICTURE: "blabla.png",
        ATTR_FRIENDLY_NAME: "REST Switch",
        ATTR_ICON: "mdi:one_two_three",
    }
