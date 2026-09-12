"""Tests for iZone sensor platform."""

from unittest.mock import Mock

from freezegun.api import FrozenDateTimeFactory
from pizone import Zone
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.izone.const import DOMAIN
from homeassistant.components.izone.coordinator import UPDATE_INTERVAL
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
import homeassistant.helpers.device_registry as dr
import homeassistant.helpers.entity_registry as er

from . import setup_integration
from .conftest import create_mock_zone

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

SUPPLY_ENTITY = "sensor.izone_controller_000000001_supply_temperature"
RETURN_ENTITY = "sensor.izone_controller_000000001_return_temperature"
CONTROL_ZONE_ENTITY = "sensor.izone_controller_000000001_control_zone"
CONTROL_ZONE_SETPOINT_ENTITY = "sensor.izone_controller_000000001_control_zone_setpoint"
CONTROLLER_CLIMATE_ENTITY = "climate.izone_controller_000000001"
ZONE_CLIMATE_ENTITY = "climate.living_room"

SENSOR_ENTITIES = (
    SUPPLY_ENTITY,
    RETURN_ENTITY,
    CONTROL_ZONE_ENTITY,
    CONTROL_ZONE_SETPOINT_ENTITY,
)


@pytest.fixture
def platforms() -> list[Platform]:
    """Only load the sensor platform for these tests."""
    return [Platform.SENSOR]


@pytest.mark.usefixtures("init_integration")
async def test_sensor_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Controller diagnostic sensors are created."""
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
async def test_control_zone_sensors_controller_owner(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_controller: Mock,
) -> None:
    """Controller owner maps to the controller climate entity and unit setpoint."""
    mock_controller.control_setpoint_owner = mock_controller
    mock_controller.control_setpoint = mock_controller.temp_setpoint

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(CONTROL_ZONE_ENTITY).state == CONTROLLER_CLIMATE_ENTITY
    assert hass.states.get(CONTROL_ZONE_SETPOINT_ENTITY).state == "24.0"


@pytest.mark.parametrize(
    ("zone_type", "setpoint", "expected_setpoint"),
    [
        pytest.param(Zone.Type.AUTO, 24.0, "24.0", id="auto"),
        pytest.param(Zone.Type.OPCL, None, STATE_UNKNOWN, id="opcl"),
    ],
)
@pytest.mark.usefixtures("mock_create_discovery")
async def test_control_zone_sensors_zone_owner(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_controller: Mock,
    mock_zones: list[Mock],
    zone_type: Zone.Type,
    setpoint: float | None,
    expected_setpoint: str,
) -> None:
    """Zone owner maps to the zone climate entity; non-AUTO setpoint is unknown."""
    mock_zones[0].type = zone_type
    mock_controller.control_setpoint_owner = mock_zones[0]
    mock_controller.control_setpoint = setpoint

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(CONTROL_ZONE_ENTITY).state == ZONE_CLIMATE_ENTITY
    assert hass.states.get(CONTROL_ZONE_SETPOINT_ENTITY).state == expected_setpoint


@pytest.mark.usefixtures("mock_create_discovery")
async def test_control_zone_sensors_unmatched_owner(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_controller: Mock,
) -> None:
    """No matching owner reports both sensors as unknown."""
    mock_controller.control_setpoint_owner = None
    mock_controller.control_setpoint = None

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(CONTROL_ZONE_ENTITY).state == STATE_UNKNOWN
    assert hass.states.get(CONTROL_ZONE_SETPOINT_ENTITY).state == STATE_UNKNOWN


@pytest.mark.usefixtures("mock_create_discovery")
async def test_control_zone_follows_climate_entity_id_rename(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_controller: Mock,
    mock_zones: list[Mock],
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Control zone sensor tracks the zone climate entity_id after a rename."""
    mock_controller.control_setpoint_owner = mock_zones[0]
    mock_controller.control_setpoint = mock_zones[0].temp_setpoint

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(CONTROL_ZONE_ENTITY).state == ZONE_CLIMATE_ENTITY

    entity_registry.async_update_entity(
        ZONE_CLIMATE_ENTITY, new_entity_id="climate.renamed_zone"
    )
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(CONTROL_ZONE_ENTITY).state == "climate.renamed_zone"


@pytest.mark.usefixtures("mock_create_discovery")
async def test_control_zone_follows_library_zone_owner(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_controller: Mock,
) -> None:
    """HA maps the library zone owner even when a CONST sibling has no temp."""
    kitchen = create_mock_zone(index=0, name="Kitchen", temp_current=19.4)
    mock_controller.zones_total = 2
    mock_controller.zones = [
        kitchen,
        create_mock_zone(
            index=1,
            name="Bypass",
            temp_current=None,
            zone_type=Zone.Type.CONST,
        ),
    ]
    mock_controller.control_setpoint_owner = kitchen
    mock_controller.control_setpoint = kitchen.temp_setpoint

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(CONTROL_ZONE_ENTITY).state == "climate.kitchen"
