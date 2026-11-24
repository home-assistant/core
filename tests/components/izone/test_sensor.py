"""Tests for iZone sensor platform."""

from unittest.mock import Mock

from pizone import Zone
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
LIVING_ROOM_RF_SIGNAL_ENTITY = "sensor.living_room_rf_signal"
LIVING_ROOM_BATTERY_ENTITY = "sensor.living_room_battery"


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


@pytest.mark.parametrize(
    ("entity_id", "disabled_by"),
    [
        pytest.param(
            LIVING_ROOM_RF_SIGNAL_ENTITY,
            er.RegistryEntryDisabler.INTEGRATION,
            id="rf_signal",
        ),
        pytest.param(LIVING_ROOM_BATTERY_ENTITY, None, id="battery"),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_wireless_sensors_enabled_default(
    entity_registry: er.EntityRegistry,
    entity_id: str,
    disabled_by: er.RegistryEntryDisabler | None,
) -> None:
    """RF signal is disabled by default; battery is enabled."""
    entry = entity_registry.async_get(entity_id)
    assert entry is not None
    assert entry.disabled_by is disabled_by


@pytest.mark.parametrize(
    ("rf_signal", "battery_level", "rf_percent", "battery_percent"),
    [
        pytest.param(
            Zone.RfSignal.FULL, Zone.BatteryLevel.FULL, "100", "100", id="full"
        ),
        pytest.param(Zone.RfSignal.HALF, Zone.BatteryLevel.HALF, "50", "50", id="half"),
        pytest.param(
            Zone.RfSignal.QUARTER, Zone.BatteryLevel.EMPTY, "25", "0", id="low"
        ),
        pytest.param(Zone.RfSignal.NONE, Zone.BatteryLevel.EMPTY, "0", "0", id="none"),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_create_discovery")
async def test_wireless_sensor_levels(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_zones: list[Mock],
    rf_signal: Zone.RfSignal,
    battery_level: Zone.BatteryLevel,
    rf_percent: str,
    battery_percent: str,
) -> None:
    """RF signal and battery enum levels map to percentages."""
    mock_zones[0].rf_signal = rf_signal
    mock_zones[0].battery_level = battery_level

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(LIVING_ROOM_RF_SIGNAL_ENTITY).state == rf_percent
    assert hass.states.get(LIVING_ROOM_BATTERY_ENTITY).state == battery_percent


@pytest.mark.parametrize(
    "sensor_type",
    [
        pytest.param(Zone.SensorType.CCTS, id="ccts"),
        pytest.param(Zone.SensorType.WIRED, id="wired"),
        pytest.param(Zone.SensorType.NONE, id="no_sensor"),
        pytest.param(None, id="v1"),
    ],
)
@pytest.mark.usefixtures("mock_create_discovery")
async def test_wireless_sensors_not_created_for_wired_zones(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_zones: list[Mock],
    entity_registry: er.EntityRegistry,
    sensor_type: Zone.SensorType | None,
) -> None:
    """Zones without a wireless sensor get no RF signal or battery sensors."""
    mock_zones[0].sensor_type = sensor_type

    await setup_integration(hass, mock_config_entry)

    assert entity_registry.async_get(LIVING_ROOM_RF_SIGNAL_ENTITY) is None
    assert entity_registry.async_get(LIVING_ROOM_BATTERY_ENTITY) is None


@pytest.mark.usefixtures("mock_create_discovery")
async def test_wireless_sensors_not_created_without_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_zones: list[Mock],
    entity_registry: er.EntityRegistry,
) -> None:
    """A wireless zone missing RF signal or battery data gets no sensor for it."""
    mock_zones[0].rf_signal = None
    mock_zones[0].battery_level = None

    await setup_integration(hass, mock_config_entry)

    assert entity_registry.async_get(LIVING_ROOM_RF_SIGNAL_ENTITY) is None
    assert entity_registry.async_get(LIVING_ROOM_BATTERY_ENTITY) is None
