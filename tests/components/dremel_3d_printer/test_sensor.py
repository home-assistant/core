"""Sensor tests for the Dremel 3D Printer integration."""

from datetime import datetime

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.dremel_3d_printer.const import DOMAIN
from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    PERCENTAGE,
    UnitOfInformation,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import UTC

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("connection", "entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test we get sensor data."""
    freezer.move_to(datetime(2023, 5, 31, 13, 30, tzinfo=UTC))
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert await async_setup_component(hass, DOMAIN, {})
    state = hass.states.get("sensor.dremel_3d45_job_phase")
    assert state.state == "building"
    state = hass.states.get("sensor.dremel_3d45_completion_time")
    assert state.state == "2023-05-31T14:32:16+00:00"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TIMESTAMP
    state = hass.states.get("sensor.dremel_3d45_progress")
    assert state.state == "13.9"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is PERCENTAGE
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    state = hass.states.get("sensor.dremel_3d45_chamber")
    assert state.state == "27"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TEMPERATURE
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is UnitOfTemperature.CELSIUS
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    state = hass.states.get("sensor.dremel_3d45_platform_temperature")
    assert state.state == "60"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TEMPERATURE
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is UnitOfTemperature.CELSIUS
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    state = hass.states.get("sensor.dremel_3d45_target_platform_temperature")
    assert state.state == "60"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TEMPERATURE
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is UnitOfTemperature.CELSIUS
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    state = hass.states.get("sensor.dremel_3d45_max_platform_temperature")
    assert state.state == "100"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TEMPERATURE
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is UnitOfTemperature.CELSIUS
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    state = hass.states.get("sensor.dremel_3d45_extruder")
    assert state.state == "230"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TEMPERATURE
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is UnitOfTemperature.CELSIUS
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    state = hass.states.get("sensor.dremel_3d45_target_extruder_temperature")
    assert state.state == "230"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TEMPERATURE
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is UnitOfTemperature.CELSIUS
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    state = hass.states.get("sensor.dremel_3d45_max_extruder_temperature")
    assert state.state == "280"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TEMPERATURE
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is UnitOfTemperature.CELSIUS
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT
    state = hass.states.get("sensor.dremel_3d45_network_build")
    assert state.state == "1"
    state = hass.states.get("sensor.dremel_3d45_filament")
    assert state.state == "ECO-ABS"
    state = hass.states.get("sensor.dremel_3d45_elapsed_time")
    assert state.state == "0"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.DURATION
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfTime.SECONDS
    state = hass.states.get("sensor.dremel_3d45_estimated_total_time")
    assert state.state == "4340"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.DURATION
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfTime.SECONDS
    state = hass.states.get("sensor.dremel_3d45_job_status")
    assert state.state == "building"
    state = hass.states.get("sensor.dremel_3d45_job_name")
    assert state.state == "D32_Imperial_Credit"
    state = hass.states.get("sensor.dremel_3d45_api_version")
    assert state.state == "1.0.2-alpha"
    state = hass.states.get("sensor.dremel_3d45_host")
    assert state.state == "1.2.3.4"
    state = hass.states.get("sensor.dremel_3d45_connection_type")
    assert state.state == "eth0"
    state = hass.states.get("sensor.dremel_3d45_available_storage")
    assert state.state == "8700"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is UnitOfInformation.MEGABYTES
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.DATA_SIZE
    state = hass.states.get("sensor.dremel_3d45_hours_used")
    assert state.state == "7"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is UnitOfTime.HOURS
