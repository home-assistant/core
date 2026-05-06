"""Test OpenAQ sensors."""

from unittest.mock import AsyncMock

from openaq import TimeoutError as OpenAQTimeoutError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    EntityCategory,
    UnitOfLength,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from . import setup_integration
from .conftest import (
    LOCATION_ID,
    make_latest,
    make_location,
    make_response,
    make_sensor,
)

from tests.common import MockConfigEntry, snapshot_platform


async def test_sensor_snapshot(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_openaq_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test OpenAQ sensor snapshots."""
    entity_registry.async_get_or_create(
        "sensor",
        "openaq",
        f"{LOCATION_ID}_distance_from_home",
        suggested_object_id="del_norte_distance_from_home_assistant",
        disabled_by=None,
    )
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_sensor_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_openaq_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test OpenAQ sensor entities."""
    await setup_integration(hass, mock_config_entry)

    pm25 = entity_registry.async_get("sensor.del_norte_pm2_5")
    assert pm25 is not None
    assert pm25.unique_id == f"{LOCATION_ID}_pm25"
    assert pm25.capabilities == {"state_class": SensorStateClass.MEASUREMENT}
    assert pm25.options == {"sensor": {"suggested_display_precision": 1}}
    assert (state := hass.states.get("sensor.del_norte_pm2_5")) is not None
    assert state.state == "12.1"
    assert state.attributes["device_class"] == SensorDeviceClass.PM25
    assert state.attributes["unit_of_measurement"] == (
        CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )

    co = entity_registry.async_get("sensor.del_norte_carbon_monoxide")
    assert co is not None
    assert co.capabilities == {"state_class": SensorStateClass.MEASUREMENT}
    assert co.options == {"sensor": {"suggested_display_precision": 2}}
    assert (state := hass.states.get("sensor.del_norte_carbon_monoxide")) is not None
    assert state.attributes["device_class"] == SensorDeviceClass.CO
    assert state.attributes["unit_of_measurement"] == CONCENTRATION_PARTS_PER_MILLION

    no2 = entity_registry.async_get("sensor.del_norte_nitrogen_dioxide")
    assert no2 is not None
    assert no2.capabilities == {"state_class": SensorStateClass.MEASUREMENT}
    assert no2.options == {"sensor": {"suggested_display_precision": 1}}
    assert (state := hass.states.get("sensor.del_norte_nitrogen_dioxide")) is not None
    assert state.attributes["unit_of_measurement"] == CONCENTRATION_PARTS_PER_BILLION

    assert entity_registry.async_get("sensor.del_norte_unsupported") is None
    distance = entity_registry.async_get(
        "sensor.del_norte_distance_from_home_assistant"
    )
    assert distance is not None
    assert distance.capabilities == {"state_class": SensorStateClass.MEASUREMENT}
    assert distance.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert distance.entity_category is EntityCategory.DIAGNOSTIC
    assert distance.original_device_class is SensorDeviceClass.DISTANCE
    assert distance.unit_of_measurement == UnitOfLength.KILOMETERS

    device = device_registry.async_get_device(
        identifiers={("openaq", str(LOCATION_ID))}
    )
    assert device is not None
    assert device.name == "Del Norte"


async def test_distance_from_home_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_openaq_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test distance from Home Assistant sensor."""
    hass.config.latitude = 35.1
    hass.config.longitude = -106.6
    entity_registry.async_get_or_create(
        "sensor",
        "openaq",
        f"{LOCATION_ID}_distance_from_home",
        suggested_object_id="del_norte_distance_from_home_assistant",
        disabled_by=None,
    )

    await setup_integration(hass, mock_config_entry)

    distance = entity_registry.async_get(
        "sensor.del_norte_distance_from_home_assistant"
    )
    assert distance is not None
    assert distance.disabled_by is None
    assert distance.options == {"sensor": {"suggested_display_precision": 1}}
    assert (state := hass.states.get("sensor.del_norte_distance_from_home_assistant"))
    assert state.state == "0.0"
    assert state.attributes["device_class"] == SensorDeviceClass.DISTANCE
    assert state.attributes["unit_of_measurement"] == UnitOfLength.KILOMETERS


async def test_distance_from_home_sensor_uses_configured_unit_system(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_openaq_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test distance from Home Assistant sensor uses the configured unit system."""
    hass.config.latitude = 35.1
    hass.config.longitude = -106.6
    hass.config.units = US_CUSTOMARY_SYSTEM
    entity_registry.async_get_or_create(
        "sensor",
        "openaq",
        f"{LOCATION_ID}_distance_from_home",
        suggested_object_id="del_norte_distance_from_home_assistant",
        disabled_by=None,
    )

    await setup_integration(hass, mock_config_entry)

    distance = entity_registry.async_get(
        "sensor.del_norte_distance_from_home_assistant"
    )
    assert distance is not None
    assert distance.unit_of_measurement == UnitOfLength.MILES
    assert (state := hass.states.get("sensor.del_norte_distance_from_home_assistant"))
    assert state.state == "0.0"
    assert state.attributes["unit_of_measurement"] == UnitOfLength.MILES


async def test_distance_from_home_sensor_unknown_without_coordinates(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_openaq_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test distance from Home Assistant sensor without valid coordinates."""
    mock_openaq_client.locations.get.return_value = make_response(
        [make_location(coordinates=(True, -106.6))]
    )
    entity_registry.async_get_or_create(
        "sensor",
        "openaq",
        f"{LOCATION_ID}_distance_from_home",
        suggested_object_id="del_norte_distance_from_home_assistant",
        disabled_by=None,
    )

    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get("sensor.del_norte_distance_from_home_assistant"))
    assert state.state == STATE_UNKNOWN


async def test_missing_latest_values_are_not_created(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_openaq_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensors without latest values are not created."""
    mock_openaq_client.locations.latest.return_value = make_response(
        [make_latest(1, 8.5), make_latest(2, None)]
    )
    mock_openaq_client.locations.sensors.return_value = make_response(
        [make_sensor(1, "pm1"), make_sensor(2, "pm25")]
    )

    await setup_integration(hass, mock_config_entry)

    assert entity_registry.async_get("sensor.del_norte_pm1") is not None
    assert entity_registry.async_get("sensor.del_norte_pm2_5") is None


async def test_entity_unavailable_on_update_failure(
    hass: HomeAssistant,
    mock_openaq_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensors become unavailable when refresh fails."""
    await setup_integration(hass, mock_config_entry)
    coordinator = next(iter(mock_config_entry.runtime_data.coordinators.values()))
    mock_openaq_client.locations.latest.side_effect = OpenAQTimeoutError("Timeout")

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert (state := hass.states.get("sensor.del_norte_pm2_5")) is not None
    assert state.state == STATE_UNAVAILABLE


async def test_entity_unknown_when_measurement_disappears(
    hass: HomeAssistant,
    mock_openaq_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensors handle measurements disappearing after setup."""
    await setup_integration(hass, mock_config_entry)
    coordinator = next(iter(mock_config_entry.runtime_data.coordinators.values()))
    mock_openaq_client.locations.latest.return_value = make_response(
        [make_latest(1, 8.5)]
    )

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert (state := hass.states.get("sensor.del_norte_pm2_5")) is not None
    assert state.state == STATE_UNKNOWN
