"""Test Prusalink sensors."""

from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from homeassistant.components.sensor import (
    ATTR_OPTIONS,
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    Platform,
    UnitOfLength,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


@pytest.fixture(autouse=True)
def setup_sensor_platform_only():
    """Only setup sensor platform."""
    with patch("homeassistant.components.prusalink.PLATFORMS", [Platform.SENSOR]):
        yield


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors_no_job(hass: HomeAssistant, mock_config_entry, mock_api) -> None:
    """Test sensors while no job active."""
    assert await async_setup_component(hass, "prusalink", {})

    state = hass.states.get("sensor.mock_title")
    assert state is not None
    assert state.state == "idle"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.ENUM
    assert state.attributes[ATTR_OPTIONS] == [
        "idle",
        "busy",
        "printing",
        "paused",
        "finished",
        "stopped",
        "error",
        "attention",
        "ready",
    ]

    state = hass.states.get("sensor.mock_title_heatbed_temperature")
    assert state is not None
    assert state.state == "41.9"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TEMPERATURE
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT

    state = hass.states.get("sensor.mock_title_nozzle_temperature")
    assert state is not None
    assert state.state == "47.8"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TEMPERATURE
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT

    state = hass.states.get("sensor.mock_title_heatbed_target_temperature")
    assert state is not None
    assert state.state == "60.5"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TEMPERATURE
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT

    state = hass.states.get("sensor.mock_title_nozzle_target_temperature")
    assert state is not None
    assert state.state == "210.1"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TEMPERATURE
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT

    state = hass.states.get("sensor.mock_title_z_height")
    assert state is not None
    assert state.state == "1.8"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfLength.MILLIMETERS
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.DISTANCE
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT

    state = hass.states.get("sensor.mock_title_print_speed")
    assert state is not None
    assert state.state == "100"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == PERCENTAGE

    state = hass.states.get("sensor.mock_title_material")
    assert state is not None
    assert state.state == "PLA"

    state = hass.states.get("sensor.mock_title_nozzle_diameter")
    assert state is not None
    assert state.state == "0.4"

    state = hass.states.get("sensor.mock_title_print_flow")
    assert state is not None
    assert state.state == "100"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == PERCENTAGE

    state = hass.states.get("sensor.mock_title_progress")
    assert state is not None
    assert state.state == "unavailable"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == "%"

    state = hass.states.get("sensor.mock_title_filename")
    assert state is not None
    assert state.state == "unavailable"

    state = hass.states.get("sensor.mock_title_print_start")
    assert state is not None
    assert state.state == "unavailable"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TIMESTAMP

    state = hass.states.get("sensor.mock_title_print_finish")
    assert state is not None
    assert state.state == "unavailable"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TIMESTAMP

    state = hass.states.get("sensor.mock_title_hotend_fan")
    assert state is not None
    assert state.state == "100"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == REVOLUTIONS_PER_MINUTE

    state = hass.states.get("sensor.mock_title_print_fan")
    assert state is not None
    assert state.state == "75"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == REVOLUTIONS_PER_MINUTE


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors_idle_job_mk3(
    hass: HomeAssistant,
    mock_config_entry,
    mock_api,
    mock_job_api_idle_mk3,
) -> None:
    """Test sensors while job state is idle (MK3)."""
    assert await async_setup_component(hass, "prusalink", {})

    state = hass.states.get("sensor.mock_title")
    assert state is not None
    assert state.state == "idle"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.ENUM
    assert state.attributes[ATTR_OPTIONS] == [
        "idle",
        "busy",
        "printing",
        "paused",
        "finished",
        "stopped",
        "error",
        "attention",
        "ready",
    ]

    state = hass.states.get("sensor.mock_title_heatbed_temperature")
    assert state is not None
    assert state.state == "41.9"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TEMPERATURE
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT

    state = hass.states.get("sensor.mock_title_nozzle_temperature")
    assert state is not None
    assert state.state == "47.8"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TEMPERATURE
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT

    state = hass.states.get("sensor.mock_title_heatbed_target_temperature")
    assert state is not None
    assert state.state == "60.5"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TEMPERATURE
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT

    state = hass.states.get("sensor.mock_title_nozzle_target_temperature")
    assert state is not None
    assert state.state == "210.1"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TEMPERATURE
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT

    state = hass.states.get("sensor.mock_title_z_height")
    assert state is not None
    assert state.state == "1.8"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfLength.MILLIMETERS
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.DISTANCE
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT

    state = hass.states.get("sensor.mock_title_print_speed")
    assert state is not None
    assert state.state == "100"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == PERCENTAGE

    state = hass.states.get("sensor.mock_title_material")
    assert state is not None
    assert state.state == "PLA"

    state = hass.states.get("sensor.mock_title_nozzle_diameter")
    assert state is not None
    assert state.state == "0.4"

    state = hass.states.get("sensor.mock_title_print_flow")
    assert state is not None
    assert state.state == "100"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == PERCENTAGE

    state = hass.states.get("sensor.mock_title_progress")
    assert state is not None
    assert state.state == "unavailable"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == "%"

    state = hass.states.get("sensor.mock_title_filename")
    assert state is not None
    assert state.state == "unavailable"

    state = hass.states.get("sensor.mock_title_print_start")
    assert state is not None
    assert state.state == "unavailable"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TIMESTAMP

    state = hass.states.get("sensor.mock_title_print_finish")
    assert state is not None
    assert state.state == "unavailable"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TIMESTAMP

    state = hass.states.get("sensor.mock_title_hotend_fan")
    assert state is not None
    assert state.state == "100"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == REVOLUTIONS_PER_MINUTE

    state = hass.states.get("sensor.mock_title_print_fan")
    assert state is not None
    assert state.state == "75"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == REVOLUTIONS_PER_MINUTE


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors_active_job(
    hass: HomeAssistant,
    mock_config_entry,
    mock_api,
    mock_get_status_printing,
    mock_job_api_printing,
) -> None:
    """Test sensors while active job."""
    with patch(
        "homeassistant.components.prusalink.sensor.utcnow",
        return_value=datetime(2022, 8, 27, 14, 0, 0, tzinfo=UTC),
    ):
        assert await async_setup_component(hass, "prusalink", {})

    state = hass.states.get("sensor.mock_title")
    assert state is not None
    assert state.state == "printing"

    state = hass.states.get("sensor.mock_title_progress")
    assert state is not None
    assert state.state == "37.0"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == "%"

    state = hass.states.get("sensor.mock_title_filename")
    assert state is not None
    assert state.state == "TabletStand3.bgcode"

    state = hass.states.get("sensor.mock_title_print_start")
    assert state is not None
    assert state.state == "2022-08-27T01:46:53+00:00"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TIMESTAMP

    state = hass.states.get("sensor.mock_title_print_finish")
    assert state is not None
    assert state.state == "2022-08-28T10:17:00+00:00"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TIMESTAMP

    state = hass.states.get("sensor.mock_title_hotend_fan")
    assert state is not None
    assert state.state == "5000"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == REVOLUTIONS_PER_MINUTE

    state = hass.states.get("sensor.mock_title_print_fan")
    assert state is not None
    assert state.state == "2500"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == REVOLUTIONS_PER_MINUTE
