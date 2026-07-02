"""Velbus event platform tests."""

from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import cast
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.event import (
    ATTR_EVENT_TYPE,
    ATTR_EVENT_TYPES,
    EventDeviceClass,
)
from homeassistant.components.velbus.event import (
    EVENT_LONG_PRESS,
    EVENT_SHORT_PRESS,
    EVENT_TYPES,
    VelbusButtonEvent,
)
from homeassistant.const import ATTR_DEVICE_CLASS, STATE_ON, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er

from . import init_integration

from tests.common import MockConfigEntry

BINARY_SENSOR_ENTITY_ID = "binary_sensor.bedroom_kid_1_buttonon"
BUTTON_ENTITY_ID = "button.bedroom_kid_1_buttonon"
EVENT_ENTITY_ID = "event.bedroom_kid_1_buttonon"
LED_ENTITY_ID = "light.bedroom_kid_1_led_buttonon"

type StatusUpdateCallback = Callable[[], Awaitable[None]]


def _event_state(hass: HomeAssistant) -> State:
    """Return the Velbus event entity state."""
    state = hass.states.get(EVENT_ENTITY_ID)
    assert state is not None
    return state


def _get_event_callback(mock_button: AsyncMock) -> StatusUpdateCallback:
    """Return the status update callback registered by the event entity."""
    for call in mock_button.on_status_update.call_args_list:
        callback = call.args[0]
        owner = getattr(callback, "__self__", None)
        if isinstance(owner, VelbusButtonEvent):
            return cast(StatusUpdateCallback, callback)
    raise AssertionError("Velbus event entity callback was not registered")


async def _setup_event_entity(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_button: AsyncMock,
) -> StatusUpdateCallback:
    """Set up only the Velbus event platform."""
    mock_button.is_closed.return_value = False
    mock_button.get_channel_info.return_value = {"long": False}
    with patch("homeassistant.components.velbus.PLATFORMS", [Platform.EVENT]):
        await init_integration(hass, config_entry)
    return _get_event_callback(mock_button)


async def _update_button(
    hass: HomeAssistant,
    mock_button: AsyncMock,
    callback: StatusUpdateCallback,
    *,
    closed: bool,
    long_pressed: bool,
) -> None:
    """Update the mocked button state and invoke its callback."""
    mock_button.is_closed.return_value = closed
    mock_button.get_channel_info.return_value = {"long": long_pressed}
    await callback()
    await hass.async_block_till_done()


def _assert_no_completed_event(hass: HomeAssistant) -> None:
    """Assert no completed press event has been emitted."""
    state = _event_state(hass)
    assert state.state == STATE_UNKNOWN
    assert state.attributes[ATTR_EVENT_TYPE] is None


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_entities(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test event entity creation."""
    with patch(
        "homeassistant.components.velbus.PLATFORMS",
        [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.EVENT, Platform.LIGHT],
    ):
        await init_integration(hass, config_entry)

    state = _event_state(hass)
    assert state.state == STATE_UNKNOWN
    assert state.attributes[ATTR_DEVICE_CLASS] == EventDeviceClass.BUTTON
    assert state.attributes[ATTR_EVENT_TYPES] == EVENT_TYPES

    binary_sensor_state = hass.states.get(BINARY_SENSOR_ENTITY_ID)
    assert binary_sensor_state is not None
    assert binary_sensor_state.state == STATE_ON

    event_entry = entity_registry.async_get(EVENT_ENTITY_ID)
    binary_sensor_entry = entity_registry.async_get(BINARY_SENSOR_ENTITY_ID)
    button_entry = entity_registry.async_get(BUTTON_ENTITY_ID)
    led_entry = entity_registry.async_get(LED_ENTITY_ID)
    assert event_entry is not None
    assert binary_sensor_entry is not None
    assert button_entry is not None
    assert led_entry is not None
    assert event_entry.unique_id == "a1b2c3d4e5f6-1"


async def test_normal_press(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_button: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a normal press emits a short press event on release."""
    callback = await _setup_event_entity(hass, config_entry, mock_button)

    await _update_button(hass, mock_button, callback, closed=True, long_pressed=False)
    _assert_no_completed_event(hass)

    freezer.tick(timedelta(milliseconds=1))
    await _update_button(hass, mock_button, callback, closed=False, long_pressed=False)
    state = _event_state(hass)
    assert state.attributes[ATTR_EVENT_TYPE] == EVENT_SHORT_PRESS
    event_state = state.state

    freezer.tick(timedelta(milliseconds=1))
    await _update_button(hass, mock_button, callback, closed=False, long_pressed=False)
    state = _event_state(hass)
    assert state.attributes[ATTR_EVENT_TYPE] == EVENT_SHORT_PRESS
    assert state.state == event_state


async def test_long_press(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_button: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a long press emits a long press event on release."""
    callback = await _setup_event_entity(hass, config_entry, mock_button)

    await _update_button(hass, mock_button, callback, closed=True, long_pressed=False)
    _assert_no_completed_event(hass)

    freezer.tick(timedelta(milliseconds=1))
    await _update_button(hass, mock_button, callback, closed=True, long_pressed=True)
    _assert_no_completed_event(hass)

    freezer.tick(timedelta(milliseconds=1))
    await _update_button(hass, mock_button, callback, closed=False, long_pressed=False)
    state = _event_state(hass)
    assert state.attributes[ATTR_EVENT_TYPE] == EVENT_LONG_PRESS


async def test_repeated_long_status(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_button: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test repeated long status callbacks emit only on release."""
    callback = await _setup_event_entity(hass, config_entry, mock_button)

    await _update_button(hass, mock_button, callback, closed=True, long_pressed=False)

    freezer.tick(timedelta(milliseconds=1))
    await _update_button(hass, mock_button, callback, closed=True, long_pressed=True)
    _assert_no_completed_event(hass)

    freezer.tick(timedelta(milliseconds=1))
    await _update_button(hass, mock_button, callback, closed=True, long_pressed=True)
    _assert_no_completed_event(hass)

    freezer.tick(timedelta(milliseconds=1))
    await _update_button(hass, mock_button, callback, closed=True, long_pressed=True)
    _assert_no_completed_event(hass)

    freezer.tick(timedelta(milliseconds=1))
    await _update_button(hass, mock_button, callback, closed=False, long_pressed=False)
    state = _event_state(hass)
    assert state.attributes[ATTR_EVENT_TYPE] == EVENT_LONG_PRESS


async def test_repeated_release_idle_updates(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_button: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test repeated idle release updates do not emit events."""
    callback = await _setup_event_entity(hass, config_entry, mock_button)

    await _update_button(hass, mock_button, callback, closed=False, long_pressed=False)
    _assert_no_completed_event(hass)

    freezer.tick(timedelta(milliseconds=1))
    await _update_button(hass, mock_button, callback, closed=False, long_pressed=False)
    _assert_no_completed_event(hass)

    freezer.tick(timedelta(milliseconds=1))
    await _update_button(hass, mock_button, callback, closed=False, long_pressed=False)
    _assert_no_completed_event(hass)


async def test_state_reset_after_long_press(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_button: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test long state is reset before the next interaction."""
    callback = await _setup_event_entity(hass, config_entry, mock_button)

    await _update_button(hass, mock_button, callback, closed=True, long_pressed=False)
    freezer.tick(timedelta(milliseconds=1))
    await _update_button(hass, mock_button, callback, closed=True, long_pressed=True)
    freezer.tick(timedelta(milliseconds=1))
    await _update_button(hass, mock_button, callback, closed=False, long_pressed=False)
    state = _event_state(hass)
    assert state.attributes[ATTR_EVENT_TYPE] == EVENT_LONG_PRESS
    long_event_state = state.state

    freezer.tick(timedelta(milliseconds=1))
    await _update_button(hass, mock_button, callback, closed=True, long_pressed=False)
    state = _event_state(hass)
    assert state.state == long_event_state
    assert state.attributes[ATTR_EVENT_TYPE] == EVENT_LONG_PRESS

    freezer.tick(timedelta(milliseconds=1))
    await _update_button(hass, mock_button, callback, closed=False, long_pressed=False)
    state = _event_state(hass)
    assert state.state != long_event_state
    assert state.attributes[ATTR_EVENT_TYPE] == EVENT_SHORT_PRESS


async def test_unload_removes_callback(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_button: AsyncMock,
) -> None:
    """Test unloading the config entry removes the event callback."""
    callbacks: list[StatusUpdateCallback] = []

    def register_callback(callback: StatusUpdateCallback) -> None:
        callbacks.append(callback)

    def remove_callback(callback: StatusUpdateCallback) -> None:
        callbacks.remove(callback)

    mock_button.on_status_update.side_effect = register_callback
    mock_button.remove_on_status_update.side_effect = remove_callback

    callback = await _setup_event_entity(hass, config_entry, mock_button)
    assert callback in callbacks

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert callback not in callbacks
    mock_button.remove_on_status_update.assert_called_once_with(callback)
