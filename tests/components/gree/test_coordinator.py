"""Tests for Gree device response tracking."""

from datetime import timedelta
from unittest.mock import Mock

from freezegun.api import FrozenDateTimeFactory
from greeclimate.exceptions import DeviceTimeoutError
from greeclimate.network import Response
import pytest
from pytest_homeassistant.common import async_fire_time_changed

from homeassistant.components.climate import HVACMode
from homeassistant.components.gree.const import UPDATE_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from .common import async_setup_gree, build_device_mock

ENTITY_ID = "climate.fake_device_1"


async def test_silent_device_stays_unavailable(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Successful sends cannot keep a silent device available or revive it."""
    await async_setup_gree(hass)

    for expected_state in (
        HVACMode.OFF,
        HVACMode.OFF,
        STATE_UNAVAILABLE,
        STATE_UNAVAILABLE,
        STATE_UNAVAILABLE,
    ):
        freezer.tick(timedelta(seconds=UPDATE_INTERVAL))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        state = hass.states.get(ENTITY_ID)
        assert state is not None
        assert state.state == expected_state


@pytest.mark.parametrize("response", [Response.DATA, Response.RESULT])
async def test_responses_sustain_and_restore_availability(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    device: Mock,
    response: Response,
) -> None:
    """Both response types sustain availability and recover a stale device."""
    await async_setup_gree(hass)

    for _ in range(4):
        freezer.tick(timedelta(seconds=UPDATE_INTERVAL))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        device().power = False
        device().callbacks[response]({"Pow": 0})
        await hass.async_block_till_done()

        state = hass.states.get(ENTITY_ID)
        assert state is not None
        assert state.state == HVACMode.OFF

    for expected_state in (HVACMode.OFF, HVACMode.OFF, STATE_UNAVAILABLE):
        freezer.tick(timedelta(seconds=UPDATE_INTERVAL))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        state = hass.states.get(ENTITY_ID)
        assert state is not None
        assert state.state == expected_state

    device().power = False
    device().callbacks[response]({"Pow": 0})
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.OFF


async def test_one_lost_response_is_tolerated(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    device: Mock,
) -> None:
    """One missed reply is tolerated and the next reply resets staleness."""
    await async_setup_gree(hass)

    for _ in range(2):
        freezer.tick(timedelta(seconds=UPDATE_INTERVAL))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        state = hass.states.get(ENTITY_ID)
        assert state is not None
        assert state.state == HVACMode.OFF

    device().power = False
    device().callbacks[Response.RESULT]({"Pow": 0})
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.OFF


async def test_repeated_send_timeouts_stay_unavailable(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    device: Mock,
) -> None:
    """Repeated send timeouts cannot alternate unavailable and available."""
    await async_setup_gree(hass)
    device().update_state.side_effect = DeviceTimeoutError

    for expected_state in (
        HVACMode.OFF,
        STATE_UNAVAILABLE,
        STATE_UNAVAILABLE,
        STATE_UNAVAILABLE,
    ):
        freezer.tick(timedelta(seconds=UPDATE_INTERVAL))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        state = hass.states.get(ENTITY_ID)
        assert state is not None
        assert state.state == expected_state


@pytest.mark.parametrize("response", [Response.DATA, Response.RESULT])
async def test_response_publishes_immediately(
    hass: HomeAssistant, device: Mock, response: Response
) -> None:
    """Both reply types immediately publish the device state to HA."""
    await async_setup_gree(hass)

    device().power = True
    device().callbacks[response]({"Pow": 1})
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.AUTO


async def test_device_availability_is_independent(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    discovery: Mock,
    device: Mock,
) -> None:
    """A responding device cannot keep a silent device available."""
    silent = build_device_mock()
    responding = build_device_mock(name="fake-device-2", mac="bbccdd223344")
    discovery.return_value.mock_devices = [silent, responding]
    device.side_effect = [silent, responding]
    await async_setup_gree(hass)

    for _ in range(4):
        freezer.tick(timedelta(seconds=UPDATE_INTERVAL))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        responding.power = False
        responding.callbacks[Response.DATA]({"Pow": 0})
        await hass.async_block_till_done()

    silent_state = hass.states.get(ENTITY_ID)
    responding_state = hass.states.get("climate.fake_device_2")
    assert silent_state is not None
    assert responding_state is not None
    assert silent_state.state == STATE_UNAVAILABLE
    assert responding_state.state == HVACMode.OFF
