"""Tests for iZone sensor platform."""

from unittest.mock import Mock

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.izone.const import DOMAIN
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
import homeassistant.helpers.device_registry as dr
import homeassistant.helpers.entity_registry as er

from . import setup_integration
from .conftest import create_mock_zone

SUPPLY_ENTITY = "sensor.izone_controller_000000001_supply_temperature"
RETURN_ENTITY = "sensor.izone_controller_000000001_return_temperature"

SENSOR_ENTITIES = (SUPPLY_ENTITY, RETURN_ENTITY)
LIVING_ROOM_DAMPER_ENTITY = "sensor.living_room_damper_position"


@pytest.fixture
def platforms() -> list[Platform]:
    """Only load the sensor platform for these tests."""
    return [Platform.SENSOR]


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_sensor_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Controller diagnostic and zone damper sensors are created."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_sensor_device_linked_to_controller(
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Diagnostic sensors are attached to the controller device."""
    controller_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "000000001"), mock_config_entry.entry_id
    )
    assert controller_device is not None

    for entity_id in SENSOR_ENTITIES:
        entry = entity_registry.async_get(entity_id)
        assert entry is not None
        assert entry.device_id == controller_device.id


@pytest.mark.usefixtures("mock_create_discovery")
async def test_sensor_unknown_when_temp_missing(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_controller: Mock,
) -> None:
    """Missing supply/return temps report as unknown."""
    mock_controller.temp_supply = None
    mock_controller.temp_return = None

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(SUPPLY_ENTITY).state == STATE_UNKNOWN
    assert hass.states.get(RETURN_ENTITY).state == STATE_UNKNOWN


@pytest.mark.usefixtures("mock_create_discovery")
async def test_damper_position_not_created_without_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_zones: list[Mock],
    entity_registry: er.EntityRegistry,
) -> None:
    """Zones that don't report a damper position get no damper sensor."""
    mock_zones[0].damper_position = None

    await setup_integration(hass, mock_config_entry)

    assert entity_registry.async_get(LIVING_ROOM_DAMPER_ENTITY) is None


@pytest.mark.parametrize(
    ("positions", "disabled_by"),
    [
        pytest.param((50, 50), er.RegistryEntryDisabler.INTEGRATION, id="all_50"),
        pytest.param((50, 35), None, id="one_moving"),
    ],
)
@pytest.mark.usefixtures("mock_create_discovery")
async def test_damper_position_enabled_when_any_zone_reports_feedback(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_controller: Mock,
    entity_registry: er.EntityRegistry,
    positions: tuple[int, int],
    disabled_by: er.RegistryEntryDisabler | None,
) -> None:
    """A constant 50 on every zone means no damper feedback, so default disabled."""
    mock_controller.zones = [
        create_mock_zone(index=0, name="Living Room", damper_position=positions[0]),
        create_mock_zone(index=1, name="Kitchen", damper_position=positions[1]),
    ]

    await setup_integration(hass, mock_config_entry)

    for entity_id in (LIVING_ROOM_DAMPER_ENTITY, "sensor.kitchen_damper_position"):
        entry = entity_registry.async_get(entity_id)
        assert entry is not None
        assert entry.disabled_by is disabled_by
