"""Test KNX binary sensor."""
from datetime import timedelta

from homeassistant.components.knx.const import CONF_STATE_ADDRESS, CONF_SYNC_STATE
from homeassistant.components.knx.schema import BinarySensorSchema
from homeassistant.const import (
    CONF_ENTITY_CATEGORY,
    CONF_NAME,
    STATE_OFF,
    STATE_ON,
    EntityCategory,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt

from .conftest import KNXTestKit

from tests.common import (
    async_capture_events,
    async_fire_time_changed,
    mock_restore_cache,
)


async def test_binary_sensor_entity_category(
    hass: HomeAssistant, knx: KNXTestKit
) -> None:
    """Test KNX binary sensor entity category."""
    await knx.setup_integration(
        {
            BinarySensorSchema.PLATFORM: [
                {
                    CONF_NAME: "test_normal",
                    CONF_STATE_ADDRESS: "1/1/1",
                    CONF_ENTITY_CATEGORY: EntityCategory.DIAGNOSTIC,
                },
            ]
        }
    )
    assert len(hass.states.async_all()) == 1

    await knx.assert_read("1/1/1")
    await knx.receive_response("1/1/1", True)

    registry = er.async_get(hass)
    entity = registry.async_get("binary_sensor.test_normal")
    assert entity.entity_category is EntityCategory.DIAGNOSTIC


async def test_binary_sensor(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test KNX binary sensor and inverted binary_sensor."""
    await knx.setup_integration(
        {
            BinarySensorSchema.PLATFORM: [
                {
                    CONF_NAME: "test_normal",
                    CONF_STATE_ADDRESS: "1/1/1",
                },
                {
                    CONF_NAME: "test_invert",
                    CONF_STATE_ADDRESS: "2/2/2",
                    BinarySensorSchema.CONF_INVERT: True,
                },
            ]
        }
    )
    assert len(hass.states.async_all()) == 2

    # StateUpdater initialize state
    await knx.assert_read("1/1/1")
    await knx.assert_read("2/2/2")
    await knx.receive_response("1/1/1", True)
    await knx.receive_response("2/2/2", False)
    state_normal = hass.states.get("binary_sensor.test_normal")
    state_invert = hass.states.get("binary_sensor.test_invert")
    assert state_normal.state is STATE_ON
    assert state_invert.state is STATE_ON

    # receive OFF telegram
    await knx.receive_write("1/1/1", False)
    await knx.receive_write("2/2/2", True)
    state_normal = hass.states.get("binary_sensor.test_normal")
    state_invert = hass.states.get("binary_sensor.test_invert")
    assert state_normal.state is STATE_OFF
    assert state_invert.state is STATE_OFF

    # receive ON telegram
    await knx.receive_write("1/1/1", True)
    await knx.receive_write("2/2/2", False)
    state_normal = hass.states.get("binary_sensor.test_normal")
    state_invert = hass.states.get("binary_sensor.test_invert")
    assert state_normal.state is STATE_ON
    assert state_invert.state is STATE_ON

    # binary_sensor does not respond to read
    await knx.receive_read("1/1/1")
    await knx.receive_read("2/2/2")
    await knx.assert_telegram_count(0)


async def test_binary_sensor_ignore_internal_state(
    hass: HomeAssistant, knx: KNXTestKit
) -> None:
    """Test KNX binary_sensor with ignore_internal_state."""
    events = async_capture_events(hass, "state_changed")

    await knx.setup_integration(
        {
            BinarySensorSchema.PLATFORM: [
                {
                    CONF_NAME: "test_normal",
                    CONF_STATE_ADDRESS: "1/1/1",
                    CONF_SYNC_STATE: False,
                },
                {
                    CONF_NAME: "test_ignore",
                    CONF_STATE_ADDRESS: "2/2/2",
                    BinarySensorSchema.CONF_IGNORE_INTERNAL_STATE: True,
                    CONF_SYNC_STATE: False,
                },
            ]
        }
    )
    assert len(hass.states.async_all()) == 2
    # binary_sensor defaults to STATE_OFF - state change form None
    assert len(events) == 2

    # receive initial ON telegram
    await knx.receive_write("1/1/1", True)
    await knx.receive_write("2/2/2", True)
    await hass.async_block_till_done()
    assert len(events) == 4

    # receive second ON telegram - ignore_internal_state shall force state_changed event
    await knx.receive_write("1/1/1", True)
    await knx.receive_write("2/2/2", True)
    await hass.async_block_till_done()
    assert len(events) == 5

    # receive first OFF telegram
    await knx.receive_write("1/1/1", False)
    await knx.receive_write("2/2/2", False)
    await hass.async_block_till_done()
    assert len(events) == 7

    # receive second OFF telegram - ignore_internal_state shall force state_changed event
    await knx.receive_write("1/1/1", False)
    await knx.receive_write("2/2/2", False)
    await hass.async_block_till_done()
    assert len(events) == 8


async def test_binary_sensor_counter(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test KNX binary_sensor with context timeout."""
    async_fire_time_changed(hass, dt.utcnow())
    events = async_capture_events(hass, "state_changed")
    context_timeout = 1

    await knx.setup_integration(
        {
            BinarySensorSchema.PLATFORM: [
                {
                    CONF_NAME: "test",
                    CONF_STATE_ADDRESS: "2/2/2",
                    BinarySensorSchema.CONF_CONTEXT_TIMEOUT: context_timeout,
                    CONF_SYNC_STATE: False,
                },
            ]
        }
    )
    assert len(hass.states.async_all()) == 1
    assert len(events) == 1
    events.pop()

    # receive initial ON telegram
    await knx.receive_write("2/2/2", True)
    await hass.async_block_till_done()
    # no change yet - still in 1 sec context (additional async_block_till_done needed for time change)
    assert len(events) == 0
    state = hass.states.get("binary_sensor.test")
    assert state.state is STATE_OFF
    assert state.attributes.get("counter") == 0
    async_fire_time_changed(hass, dt.utcnow() + timedelta(seconds=context_timeout))
    await hass.async_block_till_done()
    await knx.xknx.task_registry.block_till_done()
    # state changed twice after context timeout - once to ON with counter 1 and once to counter 0
    state = hass.states.get("binary_sensor.test")
    assert state.state is STATE_ON
    assert state.attributes.get("counter") == 0
    # additional async_block_till_done needed event capture
    await hass.async_block_till_done()
    assert len(events) == 2
    event = events.pop(0).data
    assert event.get("new_state").attributes.get("counter") == 1
    assert event.get("old_state").attributes.get("counter") == 0
    event = events.pop(0).data
    assert event.get("new_state").attributes.get("counter") == 0
    assert event.get("old_state").attributes.get("counter") == 1

    # receive 2 telegrams in context
    await knx.receive_write("2/2/2", True)
    await knx.receive_write("2/2/2", True)
    assert len(events) == 0
    state = hass.states.get("binary_sensor.test")
    assert state.state is STATE_ON
    assert state.attributes.get("counter") == 0
    async_fire_time_changed(hass, dt.utcnow() + timedelta(seconds=context_timeout))
    await knx.xknx.task_registry.block_till_done()
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test")
    assert state.state is STATE_ON
    assert state.attributes.get("counter") == 0
    assert len(events) == 2
    event = events.pop(0).data
    assert event.get("new_state").attributes.get("counter") == 2
    assert event.get("old_state").attributes.get("counter") == 0
    event = events.pop(0).data
    assert event.get("new_state").attributes.get("counter") == 0
    assert event.get("old_state").attributes.get("counter") == 2


async def test_binary_sensor_reset(hass: HomeAssistant, knx: KNXTestKit) -> None:
    """Test KNX binary_sensor with reset_after function."""
    async_fire_time_changed(hass, dt.utcnow())

    await knx.setup_integration(
        {
            BinarySensorSchema.PLATFORM: [
                {
                    CONF_NAME: "test",
                    CONF_STATE_ADDRESS: "2/2/2",
                    BinarySensorSchema.CONF_RESET_AFTER: 1,
                    CONF_SYNC_STATE: False,
                },
            ]
        }
    )
    assert len(hass.states.async_all()) == 1

    # receive ON telegram
    await knx.receive_write("2/2/2", True)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test")
    assert state.state is STATE_ON
    async_fire_time_changed(hass, dt.utcnow() + timedelta(seconds=1))
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    # state reset after after timeout
    state = hass.states.get("binary_sensor.test")
    assert state.state is STATE_OFF


async def test_binary_sensor_restore_and_respond(hass: HomeAssistant, knx) -> None:
    """Test restoring KNX binary sensor state and respond to read."""
    _ADDRESS = "2/2/2"
    fake_state = State("binary_sensor.test", STATE_ON)
    mock_restore_cache(hass, (fake_state,))

    await knx.setup_integration(
        {
            BinarySensorSchema.PLATFORM: [
                {
                    CONF_NAME: "test",
                    CONF_STATE_ADDRESS: _ADDRESS,
                    CONF_SYNC_STATE: False,
                },
            ]
        }
    )

    # restored state - doesn't send telegram
    state = hass.states.get("binary_sensor.test")
    assert state.state == STATE_ON
    await knx.assert_telegram_count(0)

    await knx.receive_write(_ADDRESS, False)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test")
    assert state.state is STATE_OFF


async def test_binary_sensor_restore_invert(hass: HomeAssistant, knx) -> None:
    """Test restoring KNX binary sensor state with invert."""
    _ADDRESS = "2/2/2"
    fake_state = State("binary_sensor.test", STATE_ON)
    mock_restore_cache(hass, (fake_state,))

    await knx.setup_integration(
        {
            BinarySensorSchema.PLATFORM: [
                {
                    CONF_NAME: "test",
                    CONF_STATE_ADDRESS: _ADDRESS,
                    BinarySensorSchema.CONF_INVERT: True,
                    CONF_SYNC_STATE: False,
                },
            ]
        }
    )

    # restored state - doesn't send telegram
    state = hass.states.get("binary_sensor.test")
    assert state.state == STATE_ON
    await knx.assert_telegram_count(0)

    # inverted is on, make sure the state is off after it
    await knx.receive_write(_ADDRESS, True)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test")
    assert state.state is STATE_OFF
