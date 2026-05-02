"""Test the Sunricher DALI sensor platform."""

from unittest.mock import MagicMock

from PySrDaliGateway import CallbackEventType
import pytest

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import find_device_listener, trigger_availability_callback

from tests.common import MockConfigEntry, SnapshotAssertion, snapshot_platform

ENTITY_ID = "sensor.illuminance_sensor_0000_20"


@pytest.fixture
def mock_devices(
    mock_illuminance_device: MagicMock, mock_light_device: MagicMock
) -> list[MagicMock]:
    """Override mock_devices to use illuminance sensor and light device."""
    return [mock_illuminance_device, mock_light_device]


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify which platforms to test."""
    return [Platform.SENSOR]


ENERGY_ENTITY_ID = "sensor.dimmer_0000_02_energy"


@pytest.mark.usefixtures("init_integration")
async def test_setup_entry(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that async_setup_entry correctly creates sensor entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    # Should have illuminance sensor and energy sensor
    assert len(entity_entries) == 2
    entity_ids = {entry.entity_id for entry in entity_entries}
    assert ENTITY_ID in entity_ids
    assert ENERGY_ENTITY_ID in entity_ids


@pytest.mark.usefixtures("init_integration")
async def test_illuminance_callback(
    hass: HomeAssistant,
    mock_illuminance_device: MagicMock,
) -> None:
    """Test IlluminanceSensor handles valid and invalid values correctly."""
    callback = find_device_listener(
        mock_illuminance_device, CallbackEventType.ILLUMINANCE_STATUS
    )

    # Valid value should update state
    callback({"illuminance_value": 500.0, "is_valid": True})
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert float(state.state) == 500.0

    # Invalid value should be ignored
    callback({"illuminance_value": 9999.0, "is_valid": False})
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert float(state.state) == 500.0


@pytest.mark.usefixtures("init_integration")
async def test_sensor_on_off(
    hass: HomeAssistant,
    mock_illuminance_device: MagicMock,
) -> None:
    """Test IlluminanceSensor handles sensor on/off callback correctly."""
    illuminance_callback = find_device_listener(
        mock_illuminance_device, CallbackEventType.ILLUMINANCE_STATUS
    )
    illuminance_callback({"illuminance_value": 250.0, "is_valid": True})
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert float(state.state) == 250.0

    on_off_callback = find_device_listener(
        mock_illuminance_device, CallbackEventType.SENSOR_ON_OFF
    )

    # Turn off sensor -> state becomes unknown
    on_off_callback(False)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN

    # Turn on sensor -> restore previous value
    on_off_callback(True)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert float(state.state) == 250.0


@pytest.mark.usefixtures("init_integration")
async def test_availability(
    hass: HomeAssistant,
    mock_illuminance_device: MagicMock,
) -> None:
    """Test availability changes are reflected in sensor entity state."""
    trigger_availability_callback(mock_illuminance_device, False)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    trigger_availability_callback(mock_illuminance_device, True)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE


@pytest.mark.usefixtures("init_integration")
async def test_energy_callback(
    hass: HomeAssistant,
    mock_light_device: MagicMock,
) -> None:
    """Test EnergySensor handles energy report callback correctly."""
    callback = find_device_listener(mock_light_device, CallbackEventType.ENERGY_REPORT)

    # Update energy value
    callback(123.45)
    await hass.async_block_till_done()

    state = hass.states.get(ENERGY_ENTITY_ID)
    assert state is not None
    assert float(state.state) == 123.45

    # Update to new value
    callback(200.0)
    await hass.async_block_till_done()

    state = hass.states.get(ENERGY_ENTITY_ID)
    assert state is not None
    assert float(state.state) == 200.0


@pytest.mark.usefixtures("init_integration")
async def test_energy_initial_state(
    hass: HomeAssistant,
) -> None:
    """Test EnergySensor initial state is unknown."""
    state = hass.states.get(ENERGY_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN


@pytest.mark.usefixtures("init_integration")
async def test_energy_availability(
    hass: HomeAssistant,
    mock_light_device: MagicMock,
) -> None:
    """Test availability changes are reflected in energy sensor state."""
    trigger_availability_callback(mock_light_device, False)
    await hass.async_block_till_done()

    state = hass.states.get(ENERGY_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    trigger_availability_callback(mock_light_device, True)
    await hass.async_block_till_done()

    state = hass.states.get(ENERGY_ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
