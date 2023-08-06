"""The tests for the REST switch platform."""
import asyncio
from http import HTTPStatus

import httpx
import pytest
import respx

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


@respx.mock
async def test_setup_failed_connect(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test setup when connection error occurs."""
    respx.get(RESOURCE).mock(side_effect=asyncio.TimeoutError())
    config = {SWITCH_DOMAIN: {CONF_PLATFORM: DOMAIN, CONF_RESOURCE: RESOURCE}}
    assert await async_setup_component(hass, SWITCH_DOMAIN, config)
    await hass.async_block_till_done()
    assert_setup_component(0, SWITCH_DOMAIN)
    assert "No route to resource/endpoint" in caplog.text


@respx.mock
async def test_setup_timeout(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test setup when connection timeout occurs."""
    respx.get(RESOURCE).mock(side_effect=asyncio.TimeoutError())
    config = {SWITCH_DOMAIN: {CONF_PLATFORM: DOMAIN, CONF_RESOURCE: RESOURCE}}
    assert await async_setup_component(hass, SWITCH_DOMAIN, config)
    await hass.async_block_till_done()
    assert_setup_component(0, SWITCH_DOMAIN)
    assert "No route to resource/endpoint" in caplog.text


@respx.mock
async def test_setup_minimum(hass: HomeAssistant) -> None:
    """Test setup with minimum configuration."""
    route = respx.get(RESOURCE) % HTTPStatus.OK
    config = {SWITCH_DOMAIN: {CONF_PLATFORM: DOMAIN, CONF_RESOURCE: RESOURCE}}
    with assert_setup_component(1, SWITCH_DOMAIN):
        assert await async_setup_component(hass, SWITCH_DOMAIN, config)
        await hass.async_block_till_done()
    assert route.call_count == 1


@respx.mock
async def test_setup_query_params(hass: HomeAssistant) -> None:
    """Test setup with query params."""
    route = respx.get("http://localhost/?search=something") % HTTPStatus.OK
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

    assert route.call_count == 1


@respx.mock
async def test_setup(hass: HomeAssistant) -> None:
    """Test setup with valid configuration."""
    route = respx.get(RESOURCE) % HTTPStatus.OK
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
    assert route.call_count == 1
    assert_setup_component(1, SWITCH_DOMAIN)


@respx.mock
async def test_setup_with_state_resource(hass: HomeAssistant) -> None:
    """Test setup with valid configuration."""
    respx.get(RESOURCE) % HTTPStatus.NOT_FOUND
    route = respx.get("http://localhost/state") % HTTPStatus.OK
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
    assert route.call_count == 1
    assert_setup_component(1, SWITCH_DOMAIN)


@respx.mock
async def test_setup_with_templated_headers_params(hass: HomeAssistant) -> None:
    """Test setup with valid configuration."""
    route = respx.get(RESOURCE) % HTTPStatus.OK
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
    assert route.call_count == 1
    last_call = route.calls[-1]
    last_request: httpx.Request = last_call.request
    assert last_request.headers.get("Accept") == CONTENT_TYPE_JSON
    assert last_request.headers.get("User-Agent") == "Mozilla/5.0"
    assert last_request.url.params["start"] == "0"
    assert last_request.url.params["end"] == "5"
    assert_setup_component(1, SWITCH_DOMAIN)


# Tests for REST switch platform.


async def _async_setup_test_switch(hass: HomeAssistant) -> None:
    respx.get(RESOURCE) % HTTPStatus.OK

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
    respx.reset()


@respx.mock
async def test_name(hass: HomeAssistant) -> None:
    """Test the name."""
    await _async_setup_test_switch(hass)

    state = hass.states.get("switch.foo")
    assert state.attributes[ATTR_FRIENDLY_NAME] == NAME


@respx.mock
async def test_device_class(hass: HomeAssistant) -> None:
    """Test the device class."""
    await _async_setup_test_switch(hass)

    state = hass.states.get("switch.foo")
    assert state.attributes[ATTR_DEVICE_CLASS] == DEVICE_CLASS


@respx.mock
async def test_is_on_before_update(hass: HomeAssistant) -> None:
    """Test is_on in initial state."""
    await _async_setup_test_switch(hass)

    state = hass.states.get("switch.foo")
    assert state.state == STATE_UNKNOWN


@respx.mock
async def test_turn_on_success(hass: HomeAssistant) -> None:
    """Test turn_on."""
    await _async_setup_test_switch(hass)

    route = respx.post(RESOURCE) % HTTPStatus.OK
    respx.get(RESOURCE).mock(side_effect=httpx.RequestError)
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.foo"},
        blocking=True,
    )
    await hass.async_block_till_done()

    last_call = route.calls[-1]
    last_request: httpx.Request = last_call.request
    assert last_request.content.decode() == "ON"
    assert hass.states.get("switch.foo").state == STATE_ON


@respx.mock
async def test_turn_on_status_not_ok(hass: HomeAssistant) -> None:
    """Test turn_on when error status returned."""
    await _async_setup_test_switch(hass)

    route = respx.post(RESOURCE) % HTTPStatus.INTERNAL_SERVER_ERROR
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.foo"},
        blocking=True,
    )
    await hass.async_block_till_done()

    last_call = route.calls[-1]
    last_request: httpx.Request = last_call.request
    assert last_request.content.decode() == "ON"
    assert hass.states.get("switch.foo").state == STATE_UNKNOWN


@respx.mock
async def test_turn_on_timeout(hass: HomeAssistant) -> None:
    """Test turn_on when timeout occurs."""
    await _async_setup_test_switch(hass)

    respx.post(RESOURCE) % HTTPStatus.INTERNAL_SERVER_ERROR
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.foo"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.get("switch.foo").state == STATE_UNKNOWN


@respx.mock
async def test_turn_off_success(hass: HomeAssistant) -> None:
    """Test turn_off."""
    await _async_setup_test_switch(hass)

    route = respx.post(RESOURCE) % HTTPStatus.OK
    respx.get(RESOURCE).mock(side_effect=httpx.RequestError)
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.foo"},
        blocking=True,
    )
    await hass.async_block_till_done()

    last_call = route.calls[-1]
    last_request: httpx.Request = last_call.request
    assert last_request.content.decode() == "OFF"

    assert hass.states.get("switch.foo").state == STATE_OFF


@respx.mock
async def test_turn_off_status_not_ok(hass: HomeAssistant) -> None:
    """Test turn_off when error status returned."""
    await _async_setup_test_switch(hass)

    route = respx.post(RESOURCE) % HTTPStatus.INTERNAL_SERVER_ERROR
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.foo"},
        blocking=True,
    )
    await hass.async_block_till_done()

    last_call = route.calls[-1]
    last_request: httpx.Request = last_call.request
    assert last_request.content.decode() == "OFF"

    assert hass.states.get("switch.foo").state == STATE_UNKNOWN


@respx.mock
async def test_turn_off_timeout(hass: HomeAssistant) -> None:
    """Test turn_off when timeout occurs."""
    await _async_setup_test_switch(hass)

    respx.post(RESOURCE).mock(side_effect=asyncio.TimeoutError())
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.foo"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.get("switch.foo").state == STATE_UNKNOWN


@respx.mock
async def test_update_when_on(hass: HomeAssistant) -> None:
    """Test update when switch is on."""
    await _async_setup_test_switch(hass)

    respx.get(RESOURCE).respond(text="ON")
    async_fire_time_changed(hass, utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()

    assert hass.states.get("switch.foo").state == STATE_ON


@respx.mock
async def test_update_when_off(hass: HomeAssistant) -> None:
    """Test update when switch is off."""
    await _async_setup_test_switch(hass)

    respx.get(RESOURCE).respond(text="OFF")
    async_fire_time_changed(hass, utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()

    assert hass.states.get("switch.foo").state == STATE_OFF


@respx.mock
async def test_update_when_unknown(hass: HomeAssistant) -> None:
    """Test update when unknown status returned."""
    await _async_setup_test_switch(hass)

    respx.get(RESOURCE).respond(text="unknown status")
    async_fire_time_changed(hass, utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()

    assert hass.states.get("switch.foo").state == STATE_UNKNOWN


@respx.mock
async def test_update_timeout(hass: HomeAssistant) -> None:
    """Test update when timeout occurs."""
    await _async_setup_test_switch(hass)

    respx.get(RESOURCE).mock(side_effect=asyncio.TimeoutError())
    async_fire_time_changed(hass, utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()

    assert hass.states.get("switch.foo").state == STATE_UNKNOWN


@respx.mock
async def test_entity_config(hass: HomeAssistant) -> None:
    """Test entity configuration."""

    respx.get(RESOURCE) % HTTPStatus.OK
    config = {
        SWITCH_DOMAIN: {
            # REST configuration
            CONF_PLATFORM: DOMAIN,
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

    async_fire_time_changed(hass, utcnow() + SCAN_INTERVAL)
    state = hass.states.get("switch.rest_switch")
    assert state.state == "unknown"
    assert state.attributes == {
        ATTR_ENTITY_PICTURE: "blabla.png",
        ATTR_FRIENDLY_NAME: "REST Switch",
        ATTR_ICON: "mdi:one_two_three",
    }
