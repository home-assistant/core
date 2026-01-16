"""Test the Sunricher DALI binary sensor platform."""

from unittest.mock import MagicMock

from PySrDaliGateway import CallbackEventType
from PySrDaliGateway.types import MotionState
import pytest

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import find_device_listener, trigger_availability_callback

from tests.common import MockConfigEntry

TEST_OCCUPANCY_ENTITY_ID = "binary_sensor.motion_sensor_0000_10"


@pytest.fixture
def mock_devices(mock_sensor_devices: list[MagicMock]) -> list[MagicMock]:
    """Override mock_devices to use sensor devices only."""
    return mock_sensor_devices


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify which platforms to test."""
    return [Platform.BINARY_SENSOR]


@pytest.mark.usefixtures("init_integration")
async def test_async_setup_entry_creates_binary_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that async_setup_entry correctly creates binary sensor entities."""
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    assert len(entity_entries) == 1

    entity_ids = [entry.entity_id for entry in entity_entries]
    assert TEST_OCCUPANCY_ENTITY_ID in entity_ids


@pytest.mark.usefixtures("init_integration")
async def test_occupancy_sensor_initial_state(
    hass: HomeAssistant,
) -> None:
    """Test occupancy sensor initial state is OFF."""
    state = hass.states.get(TEST_OCCUPANCY_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF


@pytest.mark.usefixtures("init_integration")
async def test_occupancy_sensor_motion_detected(
    hass: HomeAssistant,
    mock_sensor_devices: list[MagicMock],
) -> None:
    """Test occupancy sensor turns ON when motion is detected."""
    motion_device = mock_sensor_devices[0]

    callback = find_device_listener(motion_device, CallbackEventType.MOTION_STATUS)

    callback({"motion_state": MotionState.MOTION})
    await hass.async_block_till_done()

    state = hass.states.get(TEST_OCCUPANCY_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON


@pytest.mark.usefixtures("init_integration")
async def test_occupancy_sensor_presence_detected(
    hass: HomeAssistant,
    mock_sensor_devices: list[MagicMock],
) -> None:
    """Test occupancy sensor turns ON when presence is detected."""
    motion_device = mock_sensor_devices[0]

    callback = find_device_listener(motion_device, CallbackEventType.MOTION_STATUS)

    callback({"motion_state": MotionState.PRESENCE})
    await hass.async_block_till_done()

    state = hass.states.get(TEST_OCCUPANCY_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON


@pytest.mark.usefixtures("init_integration")
async def test_occupancy_sensor_occupancy_detected(
    hass: HomeAssistant,
    mock_sensor_devices: list[MagicMock],
) -> None:
    """Test occupancy sensor turns ON when occupancy is detected."""
    motion_device = mock_sensor_devices[0]

    callback = find_device_listener(motion_device, CallbackEventType.MOTION_STATUS)

    callback({"motion_state": MotionState.OCCUPANCY})
    await hass.async_block_till_done()

    state = hass.states.get(TEST_OCCUPANCY_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON


@pytest.mark.usefixtures("init_integration")
async def test_occupancy_sensor_no_motion(
    hass: HomeAssistant,
    mock_sensor_devices: list[MagicMock],
) -> None:
    """Test occupancy sensor turns OFF when no motion."""
    motion_device = mock_sensor_devices[0]

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
    assert state.state == STATE_OFF


@pytest.mark.usefixtures("init_integration")
async def test_occupancy_sensor_vacant(
    hass: HomeAssistant,
    mock_sensor_devices: list[MagicMock],
) -> None:
    """Test occupancy sensor turns OFF when vacant."""
    motion_device = mock_sensor_devices[0]

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
    mock_sensor_devices: list[MagicMock],
) -> None:
    """Test availability changes are reflected in binary sensor entity state."""
    motion_device = mock_sensor_devices[0]

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
