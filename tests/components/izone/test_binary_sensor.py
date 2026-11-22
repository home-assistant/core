"""Tests for iZone binary sensor platform."""

from unittest.mock import Mock

from pizone import Zone
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
import homeassistant.helpers.entity_registry as er

from . import setup_integration

LIVING_ROOM_DAMPER_FAULT_ENTITY = "binary_sensor.living_room_damper_fault"
LIVING_ROOM_SENSOR_FAULT_ENTITY = "binary_sensor.living_room_sensor_fault"


@pytest.fixture
def platforms() -> list[Platform]:
    """Only load the binary sensor platform for these tests."""
    return [Platform.BINARY_SENSOR]


@pytest.mark.usefixtures("init_integration")
async def test_binary_sensor_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Zone damper and sensor fault binary sensors are created."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("damper_fault", "sensor_fault", "damper_state", "sensor_state"),
    [
        pytest.param(True, False, STATE_ON, STATE_OFF, id="damper_fault"),
        pytest.param(False, True, STATE_OFF, STATE_ON, id="sensor_fault"),
    ],
)
@pytest.mark.usefixtures("mock_create_discovery")
async def test_fault_states(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_zones: list[Mock],
    damper_fault: bool,
    sensor_fault: bool,
    damper_state: str,
    sensor_state: str,
) -> None:
    """Zone fault flags map to binary sensor states."""
    mock_zones[0].damper_fault = damper_fault
    mock_zones[0].sensor_fault = sensor_fault

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(LIVING_ROOM_DAMPER_FAULT_ENTITY).state == damper_state
    assert hass.states.get(LIVING_ROOM_SENSOR_FAULT_ENTITY).state == sensor_state


@pytest.mark.usefixtures("mock_create_discovery")
async def test_damper_fault_not_created_without_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_zones: list[Mock],
    entity_registry: er.EntityRegistry,
) -> None:
    """Zones that don't report a damper fault get no damper fault sensor."""
    mock_zones[0].damper_fault = None

    await setup_integration(hass, mock_config_entry)

    assert entity_registry.async_get(LIVING_ROOM_DAMPER_FAULT_ENTITY) is None


@pytest.mark.parametrize(
    ("sensor_fault", "sensor_type"),
    [
        pytest.param(None, None, id="v1"),
        pytest.param(False, Zone.SensorType.NONE, id="no_sensor"),
    ],
)
@pytest.mark.usefixtures("mock_create_discovery")
async def test_sensor_fault_not_created(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_zones: list[Mock],
    entity_registry: er.EntityRegistry,
    sensor_fault: bool | None,
    sensor_type: Zone.SensorType | None,
) -> None:
    """Zones without a sensor fault reading or without a sensor get no sensor fault."""
    mock_zones[0].sensor_fault = sensor_fault
    mock_zones[0].sensor_type = sensor_type

    await setup_integration(hass, mock_config_entry)

    assert entity_registry.async_get(LIVING_ROOM_SENSOR_FAULT_ENTITY) is None
