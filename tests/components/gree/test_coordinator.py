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


async def test_no_response(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, device: Mock
) -> None:
    """Successful sends cannot keep a silent device available or revive it."""
    await async_setup_gree(hass)
    device().update_state.reset_mock()

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

    assert device().update_state.await_count == 5


@pytest.mark.parametrize("response", [Response.DATA, Response.RESULT])
async def test_responses_keep_device_available(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    device: Mock,
    response: Response,
) -> None:
    """Both poll replies and command acknowledgments prove the device is alive."""
    await async_setup_gree(hass)
    handlers = {
        call.args[0]: call.args[1] for call in device().add_handler.call_args_list
    }

    for _ in range(5):
        freezer.tick(timedelta(seconds=UPDATE_INTERVAL))
        handlers[response]({"Pow": 0})
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        state = hass.states.get(ENTITY_ID)
        assert state is not None
        assert state.state == HVACMode.OFF


@pytest.mark.parametrize("response", [Response.DATA, Response.RESULT])
async def test_response_recovery(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    device: Mock,
    response: Response,
) -> None:
    """A real response restores availability after a prolonged silence."""
    await async_setup_gree(hass)
    handlers = {
        call.args[0]: call.args[1] for call in device().add_handler.call_args_list
    }

    for _ in range(4):
        freezer.tick(timedelta(seconds=UPDATE_INTERVAL))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    freezer.tick(timedelta(seconds=UPDATE_INTERVAL))
    handlers[response]({"Pow": 0})
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.OFF


async def test_single_lost_response(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, device: Mock
) -> None:
    """A single lost reply does not make the device unavailable."""
    await async_setup_gree(hass)
    handlers = {
        call.args[0]: call.args[1] for call in device().add_handler.call_args_list
    }

    freezer.tick(timedelta(seconds=UPDATE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.OFF

    freezer.tick(timedelta(seconds=UPDATE_INTERVAL))
    handlers[Response.DATA]({"Pow": 0})
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.OFF


async def test_repeated_send_timeouts(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, device: Mock
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


@pytest.mark.parametrize(
    ("response", "expected_state"),
    [(Response.DATA, HVACMode.OFF), (Response.RESULT, HVACMode.AUTO)],
)
async def test_response_publication(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    device: Mock,
    response: Response,
    expected_state: str,
) -> None:
    """Only command replies publish immediately; polling still publishes DATA."""
    await async_setup_gree(hass)
    handlers = {
        call.args[0]: call.args[1] for call in device().add_handler.call_args_list
    }

    device().power = True
    handlers[response]({"Pow": 1})
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == expected_state

    freezer.tick(timedelta(seconds=UPDATE_INTERVAL))
    async_fire_time_changed(hass)
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
    handlers = {
        call.args[0]: call.args[1] for call in responding.add_handler.call_args_list
    }

    for _ in range(4):
        freezer.tick(timedelta(seconds=UPDATE_INTERVAL))
        handlers[Response.DATA]({"Pow": 0})
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    silent_state = hass.states.get(ENTITY_ID)
    responding_state = hass.states.get("climate.fake_device_2")
    assert silent_state is not None
    assert responding_state is not None
    assert silent_state.state == STATE_UNAVAILABLE
    assert responding_state.state == HVACMode.OFF
