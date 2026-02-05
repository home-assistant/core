"""Test the Sunricher DALI binary sensor platform."""

from unittest.mock import MagicMock

from PySrDaliGateway import CallbackEventType
from PySrDaliGateway.types import MotionState
import pytest

from homeassistant.const import (
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import find_device_listener, trigger_availability_callback

from tests.common import MockConfigEntry, SnapshotAssertion, snapshot_platform

TEST_MOTION_ENTITY_ID = "binary_sensor.motion_sensor_0000_10_motion"
TEST_OCCUPANCY_ENTITY_ID = "binary_sensor.motion_sensor_0000_10_occupancy"


@pytest.fixture
def mock_devices(mock_motion_sensor_device: MagicMock) -> list[MagicMock]:
    """Override mock_devices to use motion sensor device only."""
    return [mock_motion_sensor_device]


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify which platforms to test."""
    return [Platform.BINARY_SENSOR]


@pytest.mark.usefixtures("init_integration")
async def test_setup_entry(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that async_setup_entry correctly creates binary sensor entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    assert len(entity_entries) == 2

    entity_ids = [entry.entity_id for entry in entity_entries]
    assert TEST_MOTION_ENTITY_ID in entity_ids
    assert TEST_OCCUPANCY_ENTITY_ID in entity_ids


@pytest.mark.usefixtures("init_integration")
async def test_occupancy_sensor_initial_state(
    hass: HomeAssistant,
) -> None:
    """Test occupancy sensor initial state is OFF."""
    state = hass.states.get(TEST_OCCUPANCY_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN


@pytest.mark.usefixtures("init_integration")
async def test_occupancy_sensor_motion_detected(
    hass: HomeAssistant,
    mock_motion_sensor_device: MagicMock,
) -> None:
    """Test occupancy sensor turns ON when motion is detected."""
    motion_device = mock_motion_sensor_device

    callback = find_device_listener(motion_device, CallbackEventType.MOTION_STATUS)

    callback({"motion_state": MotionState.MOTION})
    await hass.async_block_till_done()

    state = hass.states.get(TEST_OCCUPANCY_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON


@pytest.mark.usefixtures("init_integration")
async def test_occupancy_sensor_presence_detected(
    hass: HomeAssistant,
    mock_motion_sensor_device: MagicMock,
) -> None:
    """Test occupancy sensor turns ON when presence is detected."""
    motion_device = mock_motion_sensor_device

    callback = find_device_listener(motion_device, CallbackEventType.MOTION_STATUS)

    callback({"motion_state": MotionState.PRESENCE})
    await hass.async_block_till_done()

    state = hass.states.get(TEST_OCCUPANCY_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON


@pytest.mark.usefixtures("init_integration")
async def test_occupancy_sensor_occupancy_detected(
    hass: HomeAssistant,
    mock_motion_sensor_device: MagicMock,
) -> None:
    """Test occupancy sensor turns ON when occupancy is detected."""
    motion_device = mock_motion_sensor_device

    callback = find_device_listener(motion_device, CallbackEventType.MOTION_STATUS)

    callback({"motion_state": MotionState.OCCUPANCY})
    await hass.async_block_till_done()

    state = hass.states.get(TEST_OCCUPANCY_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON


@pytest.mark.usefixtures("init_integration")
async def test_occupancy_sensor_ignores_no_motion(
    hass: HomeAssistant,
    mock_motion_sensor_device: MagicMock,
) -> None:
    """Test occupancy sensor stays ON after NO_MOTION (only VACANT turns it off)."""
    motion_device = mock_motion_sensor_device

    callback = find_device_listener(motion_device, CallbackEventType.MOTION_STATUS)

    callback({"motion_state": MotionState.MOTION})
    await hass.async_block_till_done()

    state = hass.states.get(TEST_OCCUPANCY_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON

    callback({"motion_state": MotionState.NO_MOTION})
    await hass.async_block_till_done()

    state = hass.states.get(TEST_OCCUPANCY_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON  # Still ON - NO_MOTION does not affect occupancy


@pytest.mark.usefixtures("init_integration")
async def test_occupancy_sensor_vacant(
    hass: HomeAssistant,
    mock_motion_sensor_device: MagicMock,
) -> None:
    """Test occupancy sensor turns OFF when vacant."""
    motion_device = mock_motion_sensor_device

    callback = find_device_listener(motion_device, CallbackEventType.MOTION_STATUS)

    callback({"motion_state": MotionState.OCCUPANCY})
    await hass.async_block_till_done()

    state = hass.states.get(TEST_OCCUPANCY_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON

    callback({"motion_state": MotionState.VACANT})
    await hass.async_block_till_done()

    state = hass.states.get(TEST_OCCUPANCY_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF


@pytest.mark.usefixtures("init_integration")
async def test_occupancy_sensor_availability(
    hass: HomeAssistant,
    mock_motion_sensor_device: MagicMock,
) -> None:
    """Test availability changes are reflected in binary sensor entity state."""
    motion_device = mock_motion_sensor_device

    trigger_availability_callback(motion_device, False)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_OCCUPANCY_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    trigger_availability_callback(motion_device, True)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_OCCUPANCY_ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE


# MotionSensor tests


@pytest.mark.usefixtures("init_integration")
async def test_motion_sensor_initial_state(
    hass: HomeAssistant,
) -> None:
    """Test motion sensor initial state is OFF."""
    state = hass.states.get(TEST_MOTION_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN


@pytest.mark.usefixtures("init_integration")
async def test_motion_sensor_on_motion(
    hass: HomeAssistant,
    mock_motion_sensor_device: MagicMock,
) -> None:
    """Test motion sensor turns ON when motion is detected."""
    motion_device = mock_motion_sensor_device

    callback = find_device_listener(motion_device, CallbackEventType.MOTION_STATUS)

    callback({"motion_state": MotionState.MOTION})
    await hass.async_block_till_done()

    state = hass.states.get(TEST_MOTION_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON


@pytest.mark.usefixtures("init_integration")
async def test_motion_sensor_off_no_motion(
    hass: HomeAssistant,
    mock_motion_sensor_device: MagicMock,
) -> None:
    """Test motion sensor turns OFF when no motion."""
    motion_device = mock_motion_sensor_device

    callback = find_device_listener(motion_device, CallbackEventType.MOTION_STATUS)

    callback({"motion_state": MotionState.MOTION})
    await hass.async_block_till_done()

    state = hass.states.get(TEST_MOTION_ENTITY_ID)
    assert state.state == STATE_ON

    callback({"motion_state": MotionState.NO_MOTION})
    await hass.async_block_till_done()

    state = hass.states.get(TEST_MOTION_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF


@pytest.mark.usefixtures("init_integration")
async def test_motion_sensor_ignores_occupancy_events(
    hass: HomeAssistant,
    mock_motion_sensor_device: MagicMock,
) -> None:
    """Test motion sensor ignores OCCUPANCY, PRESENCE, VACANT events."""
    motion_device = mock_motion_sensor_device

    callback = find_device_listener(motion_device, CallbackEventType.MOTION_STATUS)

    # Start with motion ON
    callback({"motion_state": MotionState.MOTION})
    await hass.async_block_till_done()
    state = hass.states.get(TEST_MOTION_ENTITY_ID)
    assert state.state == STATE_ON

    # OCCUPANCY should not change motion sensor
    callback({"motion_state": MotionState.OCCUPANCY})
    await hass.async_block_till_done()
    state = hass.states.get(TEST_MOTION_ENTITY_ID)
    assert state.state == STATE_ON

    # PRESENCE should not change motion sensor
    callback({"motion_state": MotionState.PRESENCE})
    await hass.async_block_till_done()
    state = hass.states.get(TEST_MOTION_ENTITY_ID)
    assert state.state == STATE_ON

    # VACANT should not change motion sensor
    callback({"motion_state": MotionState.VACANT})
    await hass.async_block_till_done()
    state = hass.states.get(TEST_MOTION_ENTITY_ID)
    assert state.state == STATE_ON
