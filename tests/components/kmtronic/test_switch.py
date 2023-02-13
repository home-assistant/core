"""The tests for the KMtronic switch platform."""
import asyncio
from datetime import timedelta
from http import HTTPStatus

from homeassistant.components.kmtronic.const import DOMAIN
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_relay_on_off(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Tests the relay turns on correctly."""

    aioclient_mock.get(
        "http://1.1.1.1/status.xml",
        text="<response><relay0>0</relay0><relay1>0</relay1></response>",
    )
    aioclient_mock.get(
        "http://1.1.1.1/relays.cgi?relay=1",
        text="OK",
    )

    MockConfigEntry(
        domain=DOMAIN, data={"host": "1.1.1.1", "username": "foo", "password": "bar"}
    ).add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    # Mocks the response for turning a relay1 on
    aioclient_mock.get(
        "http://1.1.1.1/FF0101",
        text="",
    )

    state = hass.states.get("switch.relay1")
    assert state.state == "off"

    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.relay1"}, blocking=True
    )

    await hass.async_block_till_done()
    state = hass.states.get("switch.relay1")
    assert state.state == "on"

    # Mocks the response for turning a relay1 off
    aioclient_mock.get(
        "http://1.1.1.1/FF0100",
        text="",
    )

    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": "switch.relay1"}, blocking=True
    )

    await hass.async_block_till_done()
    state = hass.states.get("switch.relay1")
    assert state.state == "off"

    # Mocks the response for turning a relay1 on
    aioclient_mock.get(
        "http://1.1.1.1/FF0101",
        text="",
    )

    await hass.services.async_call(
        "switch", "toggle", {"entity_id": "switch.relay1"}, blocking=True
    )

    await hass.async_block_till_done()
    state = hass.states.get("switch.relay1")
    assert state.state == "on"


async def test_update(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Tests switch refreshes status periodically."""
    now = dt_util.utcnow()
    future = now + timedelta(minutes=10)

    aioclient_mock.get(
        "http://1.1.1.1/status.xml",
        text="<response><relay0>0</relay0><relay1>0</relay1></response>",
    )

    MockConfigEntry(
        domain=DOMAIN, data={"host": "1.1.1.1", "username": "foo", "password": "bar"}
    ).add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})

    await hass.async_block_till_done()
    state = hass.states.get("switch.relay1")
    assert state.state == "off"

    aioclient_mock.clear_requests()
    aioclient_mock.get(
        "http://1.1.1.1/status.xml",
        text="<response><relay0>1</relay0><relay1>1</relay1></response>",
    )
    async_fire_time_changed(hass, future)

    await hass.async_block_till_done()
    state = hass.states.get("switch.relay1")
    assert state.state == "on"


async def test_failed_update(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Tests coordinator update fails."""
    now = dt_util.utcnow()
    future = now + timedelta(minutes=10)

    aioclient_mock.get(
        "http://1.1.1.1/status.xml",
        text="<response><relay0>0</relay0><relay1>0</relay1></response>",
    )

    MockConfigEntry(
        domain=DOMAIN, data={"host": "1.1.1.1", "username": "foo", "password": "bar"}
    ).add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})

    await hass.async_block_till_done()
    state = hass.states.get("switch.relay1")
    assert state.state == "off"

    aioclient_mock.clear_requests()
    aioclient_mock.get(
        "http://1.1.1.1/status.xml",
        text="401 Unauthorized: Password required",
        status=HTTPStatus.UNAUTHORIZED,
    )
    async_fire_time_changed(hass, future)

    await hass.async_block_till_done()
    state = hass.states.get("switch.relay1")
    assert state.state == STATE_UNAVAILABLE

    future += timedelta(minutes=10)
    aioclient_mock.clear_requests()
    aioclient_mock.get(
        "http://1.1.1.1/status.xml",
        exc=asyncio.TimeoutError(),
    )
    async_fire_time_changed(hass, future)

    await hass.async_block_till_done()
    state = hass.states.get("switch.relay1")
    assert state.state == STATE_UNAVAILABLE


async def test_relay_on_off_reversed(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Tests the relay turns on correctly when configured as reverse."""

    aioclient_mock.get(
        "http://1.1.1.1/status.xml",
        text="<response><relay0>0</relay0><relay1>0</relay1></response>",
    )

    MockConfigEntry(
        domain=DOMAIN,
        data={"host": "1.1.1.1", "username": "foo", "password": "bar"},
        options={"reverse": True},
    ).add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    # Mocks the response for turning a relay1 off
    aioclient_mock.get(
        "http://1.1.1.1/FF0101",
        text="",
    )

    state = hass.states.get("switch.relay1")
    assert state.state == "on"

    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": "switch.relay1"}, blocking=True
    )

    await hass.async_block_till_done()
    state = hass.states.get("switch.relay1")
    assert state.state == "off"

    # Mocks the response for turning a relay1 off
    aioclient_mock.get(
        "http://1.1.1.1/FF0100",
        text="",
    )

    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.relay1"}, blocking=True
    )

    await hass.async_block_till_done()
    state = hass.states.get("switch.relay1")
    assert state.state == "on"
