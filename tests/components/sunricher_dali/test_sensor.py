"""Test the Sunricher DALI sensor platform."""

from unittest.mock import MagicMock

from PySrDaliGateway import CallbackEventType
from PySrDaliGateway.types import MotionState
import pytest

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import find_device_listener, trigger_availability_callback

from tests.common import MockConfigEntry

# Entity IDs without "_state" suffix because _attr_name = None
TEST_MOTION_ENTITY_ID = "sensor.motion_sensor_0000_10"
TEST_ILLUMINANCE_ENTITY_ID = "sensor.illuminance_sensor_0000_20"


@pytest.fixture
def mock_devices(mock_sensor_devices: list[MagicMock]) -> list[MagicMock]:
    """Override mock_devices to use sensor devices only."""
    return mock_sensor_devices


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify which platforms to test."""
    return [Platform.SENSOR]


@pytest.mark.usefixtures("init_integration")
async def test_async_setup_entry_creates_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that async_setup_entry correctly creates sensor entities."""
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    assert len(entity_entries) == 2

    entity_ids = [entry.entity_id for entry in entity_entries]
    assert TEST_MOTION_ENTITY_ID in entity_ids
    assert TEST_ILLUMINANCE_ENTITY_ID in entity_ids


@pytest.mark.usefixtures("init_integration")
async def test_motion_sensor_callback(
    hass: HomeAssistant,
    mock_sensor_devices: list[MagicMock],
) -> None:
    """Test MotionSensor handles motion status callback correctly."""
    motion_device = mock_sensor_devices[0]

    state = hass.states.get(TEST_MOTION_ENTITY_ID)
    assert state is not None
    assert state.state == "no_motion"

    callback = find_device_listener(motion_device, CallbackEventType.MOTION_STATUS)

    callback({"motion_state": MotionState.MOTION})
    await hass.async_block_till_done()

    state = hass.states.get(TEST_MOTION_ENTITY_ID)
    assert state is not None
    assert state.state == "motion"

    callback({"motion_state": MotionState.PRESENCE})
    await hass.async_block_till_done()

    state = hass.states.get(TEST_MOTION_ENTITY_ID)
    assert state is not None
    assert state.state == "presence"


@pytest.mark.usefixtures("init_integration")
async def test_illuminance_sensor_callback(
    hass: HomeAssistant,
    mock_sensor_devices: list[MagicMock],
) -> None:
    """Test IlluminanceSensor handles illuminance status callback correctly."""
    illuminance_device = mock_sensor_devices[1]

    state = hass.states.get(TEST_ILLUMINANCE_ENTITY_ID)
    assert state is not None

    callback = find_device_listener(
        illuminance_device, CallbackEventType.ILLUMINANCE_STATUS
    )

    callback({"illuminance_value": 500.0, "is_valid": True})
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ILLUMINANCE_ENTITY_ID)
    assert state is not None
    assert float(state.state) == 500.0


@pytest.mark.usefixtures("init_integration")
async def test_illuminance_sensor_invalid_value_filtered(
    hass: HomeAssistant,
    mock_sensor_devices: list[MagicMock],
) -> None:
    """Test IlluminanceSensor filters out invalid values."""
    illuminance_device = mock_sensor_devices[1]

    callback = find_device_listener(
        illuminance_device, CallbackEventType.ILLUMINANCE_STATUS
    )

    callback({"illuminance_value": 300.0, "is_valid": True})
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ILLUMINANCE_ENTITY_ID)
    assert state is not None
    assert float(state.state) == 300.0

    callback({"illuminance_value": 9999.0, "is_valid": False})
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ILLUMINANCE_ENTITY_ID)
    assert state is not None
    assert float(state.state) == 300.0


@pytest.mark.usefixtures("init_integration")
async def test_illuminance_sensor_on_off_callback(
    hass: HomeAssistant,
    mock_sensor_devices: list[MagicMock],
) -> None:
    """Test IlluminanceSensor handles sensor on/off callback correctly."""
    illuminance_device = mock_sensor_devices[1]

    illuminance_callback = find_device_listener(
        illuminance_device, CallbackEventType.ILLUMINANCE_STATUS
    )
    illuminance_callback({"illuminance_value": 250.0, "is_valid": True})
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ILLUMINANCE_ENTITY_ID)
    assert state is not None
    assert float(state.state) == 250.0

    on_off_callback = find_device_listener(
        illuminance_device, CallbackEventType.SENSOR_ON_OFF
    )

    # Disable sensor -> state becomes unknown
    on_off_callback(False)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ILLUMINANCE_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN

    # Enable sensor -> stored value should be restored
    on_off_callback(True)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_ILLUMINANCE_ENTITY_ID)
    assert state is not None
    assert float(state.state) == 250.0


@pytest.mark.usefixtures("init_integration")
async def test_sensor_availability(
    hass: HomeAssistant,
    mock_sensor_devices: list[MagicMock],
) -> None:
    """Test availability changes are reflected in sensor entity state."""
    motion_device = mock_sensor_devices[0]

    trigger_availability_callback(motion_device, False)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_MOTION_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    trigger_availability_callback(motion_device, True)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_MOTION_ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
