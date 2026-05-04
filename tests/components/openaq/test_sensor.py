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
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration
from .conftest import LOCATION_ID, make_latest, make_response, make_sensor

from tests.common import MockConfigEntry, snapshot_platform


async def test_sensor_snapshot(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_openaq_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test OpenAQ sensor snapshots."""
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
    assert (state := hass.states.get("sensor.del_norte_pm2_5")) is not None
    assert state.state == "12.1"
    assert state.attributes["device_class"] == SensorDeviceClass.PM25
    assert state.attributes["unit_of_measurement"] == (
        CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    )

    co = entity_registry.async_get("sensor.del_norte_carbon_monoxide")
    assert co is not None
    assert (state := hass.states.get("sensor.del_norte_carbon_monoxide")) is not None
    assert state.attributes["device_class"] == SensorDeviceClass.CO
    assert state.attributes["unit_of_measurement"] == CONCENTRATION_PARTS_PER_MILLION

    no2 = entity_registry.async_get("sensor.del_norte_nitrogen_dioxide")
    assert no2 is not None
    assert (state := hass.states.get("sensor.del_norte_nitrogen_dioxide")) is not None
    assert state.attributes["unit_of_measurement"] == CONCENTRATION_PARTS_PER_BILLION

    assert entity_registry.async_get("sensor.del_norte_unsupported") is None

    device = device_registry.async_get_device(
        identifiers={("openaq", str(LOCATION_ID))}
    )
    assert device is not None
    assert device.name == "Del Norte"


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
