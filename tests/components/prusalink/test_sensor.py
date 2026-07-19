"""Test Prusalink sensors."""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.prusalink import DOMAIN
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
    UnitOfMass,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def setup_sensor_platform_only():
    """Only setup sensor platform."""
    with patch("homeassistant.components.prusalink.PLATFORMS", [Platform.SENSOR]):
        yield


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors_no_job(hass: HomeAssistant, mock_config_entry, mock_api) -> None:
    """Test sensors while no job active."""
    assert await async_setup_component(hass, DOMAIN, {})

    state = hass.states.get("sensor.workshop_mock_title")
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

    state = hass.states.get("sensor.workshop_mock_title_heatbed_temperature")
    assert state is not None
    assert state.state == "41.9"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TEMPERATURE
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT

    state = hass.states.get("sensor.workshop_mock_title_nozzle_temperature")
    assert state is not None
    assert state.state == "47.8"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TEMPERATURE
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT

    state = hass.states.get("sensor.workshop_mock_title_heatbed_target_temperature")
    assert state is not None
    assert state.state == "60.5"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TEMPERATURE
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT

    state = hass.states.get("sensor.workshop_mock_title_nozzle_target_temperature")
    assert state is not None
    assert state.state == "210.1"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TEMPERATURE
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT

    state = hass.states.get("sensor.workshop_mock_title_z_height")
    assert state is not None
    assert state.state == "1.8"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfLength.MILLIMETERS
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.DISTANCE
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT

    state = hass.states.get("sensor.workshop_mock_title_print_speed")
    assert state is not None
    assert state.state == "100"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == PERCENTAGE

    state = hass.states.get("sensor.workshop_mock_title_material")
    assert state is not None
    assert state.state == "PLA"

    state = hass.states.get("sensor.workshop_mock_title_nozzle_diameter")
    assert state is not None
    assert state.state == "0.4"

    state = hass.states.get("sensor.workshop_mock_title_print_flow")
    assert state is not None
    assert state.state == "100"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == PERCENTAGE

    state = hass.states.get("sensor.workshop_mock_title_progress")
    assert state is not None
    assert state.state == "unavailable"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == "%"

    state = hass.states.get("sensor.workshop_mock_title_filename")
    assert state is not None
    assert state.state == "unavailable"

    state = hass.states.get("sensor.workshop_mock_title_print_start")
    assert state is not None
    assert state.state == "unavailable"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TIMESTAMP

    state = hass.states.get("sensor.workshop_mock_title_print_finish")
    assert state is not None
    assert state.state == "unavailable"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TIMESTAMP

    state = hass.states.get("sensor.workshop_mock_title_hotend_fan")
    assert state is not None
    assert state.state == "100"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == REVOLUTIONS_PER_MINUTE

    state = hass.states.get("sensor.workshop_mock_title_print_fan")
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
    assert await async_setup_component(hass, DOMAIN, {})

    state = hass.states.get("sensor.workshop_mock_title")
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

    state = hass.states.get("sensor.workshop_mock_title_heatbed_temperature")
    assert state is not None
    assert state.state == "41.9"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TEMPERATURE
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT

    state = hass.states.get("sensor.workshop_mock_title_nozzle_temperature")
    assert state is not None
    assert state.state == "47.8"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TEMPERATURE
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT

    state = hass.states.get("sensor.workshop_mock_title_heatbed_target_temperature")
    assert state is not None
    assert state.state == "60.5"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TEMPERATURE
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT

    state = hass.states.get("sensor.workshop_mock_title_nozzle_target_temperature")
    assert state is not None
    assert state.state == "210.1"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TEMPERATURE
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT

    state = hass.states.get("sensor.workshop_mock_title_z_height")
    assert state is not None
    assert state.state == "1.8"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfLength.MILLIMETERS
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.DISTANCE
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT

    state = hass.states.get("sensor.workshop_mock_title_print_speed")
    assert state is not None
    assert state.state == "100"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == PERCENTAGE

    state = hass.states.get("sensor.workshop_mock_title_material")
    assert state is not None
    assert state.state == "PLA"

    state = hass.states.get("sensor.workshop_mock_title_nozzle_diameter")
    assert state is not None
    assert state.state == "0.4"

    state = hass.states.get("sensor.workshop_mock_title_print_flow")
    assert state is not None
    assert state.state == "100"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == PERCENTAGE

    state = hass.states.get("sensor.workshop_mock_title_progress")
    assert state is not None
    assert state.state == "unavailable"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == "%"

    state = hass.states.get("sensor.workshop_mock_title_filename")
    assert state is not None
    assert state.state == "unavailable"

    state = hass.states.get("sensor.workshop_mock_title_print_start")
    assert state is not None
    assert state.state == "unavailable"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TIMESTAMP

    state = hass.states.get("sensor.workshop_mock_title_print_finish")
    assert state is not None
    assert state.state == "unavailable"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TIMESTAMP

    state = hass.states.get("sensor.workshop_mock_title_hotend_fan")
    assert state is not None
    assert state.state == "100"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == REVOLUTIONS_PER_MINUTE

    state = hass.states.get("sensor.workshop_mock_title_print_fan")
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
        assert await async_setup_component(hass, DOMAIN, {})

    state = hass.states.get("sensor.workshop_mock_title")
    assert state is not None
    assert state.state == "printing"

    state = hass.states.get("sensor.workshop_mock_title_progress")
    assert state is not None
    assert state.state == "37.0"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == "%"

    state = hass.states.get("sensor.workshop_mock_title_filename")
    assert state is not None
    assert state.state == "TabletStand3.bgcode"

    state = hass.states.get("sensor.workshop_mock_title_print_start")
    assert state is not None
    assert state.state == "2022-08-27T01:46:53+00:00"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TIMESTAMP

    state = hass.states.get("sensor.workshop_mock_title_print_finish")
    assert state is not None
    assert state.state == "2022-08-28T10:17:00+00:00"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TIMESTAMP

    state = hass.states.get("sensor.workshop_mock_title_hotend_fan")
    assert state is not None
    assert state.state == "5000"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == REVOLUTIONS_PER_MINUTE

    state = hass.states.get("sensor.workshop_mock_title_print_fan")
    assert state is not None
    assert state.state == "2500"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == REVOLUTIONS_PER_MINUTE


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_file_metadata_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: None,
    mock_get_status_printing: dict[str, Any],
    mock_job_api_printing: dict[str, Any],
    mock_file_metadata_api: dict[str, Any],
) -> None:
    """Test print file metadata sensors."""
    mock_file_metadata_api.update(
        {
            "filament_used_g": 24.41,
            "filament_used_mm": 8184.17,
            "filament_used_cm3": 19.69,
            "filament_cost": 0.68,
            "filament_type": "PLA",
            "estimated_printing_time_normal": 3811,
            "estimated_printing_time_silent": 4256,
        }
    )

    assert await async_setup_component(hass, DOMAIN, {})

    state = hass.states.get("sensor.workshop_mock_title_filament_used_weight")
    assert state is not None
    assert state.state == "24.41"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfMass.GRAMS
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.WEIGHT
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT

    state = hass.states.get("sensor.workshop_mock_title_filament_used_length")
    assert state is not None
    assert state.state == "8.18417"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfLength.METERS
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.DISTANCE
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT

    state = hass.states.get("sensor.workshop_mock_title_filament_used_volume")
    assert state is not None
    assert state.state == "19.69"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfVolume.MILLILITERS
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.VOLUME
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT

    state = hass.states.get("sensor.workshop_mock_title_filament_cost")
    assert state is not None
    assert state.state == "0.68"

    state = hass.states.get("sensor.workshop_mock_title_file_filament_type")
    assert state is not None
    assert state.state == "PLA"

    state = hass.states.get("sensor.workshop_mock_title_estimated_printing_time")
    assert state is not None
    assert state.state == "3811"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTime.SECONDS
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.DURATION
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT

    state = hass.states.get("sensor.workshop_mock_title_estimated_silent_printing_time")
    assert state is not None
    assert state.state == "4256"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTime.SECONDS
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.DURATION
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT


async def test_file_metadata_not_fetched_when_sensors_disabled(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: None,
    mock_get_status_printing: dict[str, Any],
    mock_job_api_printing: dict[str, Any],
) -> None:
    """Test disabled-by-default metadata sensors do not download the print file."""
    with patch("pyprusalink.PrusaLink.get_file_metadata") as get_file_metadata:
        assert await async_setup_component(hass, DOMAIN, {})

    assert hass.states.get("sensor.workshop_mock_title_filament_used_weight") is None
    get_file_metadata.assert_not_called()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_file_metadata_sensors_from_job_meta(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: None,
    mock_get_status_printing: dict[str, Any],
    mock_job_api_printing: dict[str, Any],
) -> None:
    """Test print file metadata sensors from job metadata."""
    mock_job_api_printing["file"]["meta"] = {
        "filament used [g]": "24.41",
        "filament_type": "PETG",
        "estimated printing time (normal mode)": "1h 3m 31s",
    }

    with patch("pyprusalink.PrusaLink.get_file_metadata") as get_file_metadata:
        assert await async_setup_component(hass, DOMAIN, {})

    state = hass.states.get("sensor.workshop_mock_title_filament_used_weight")
    assert state is not None
    assert state.state == "24.41"

    state = hass.states.get("sensor.workshop_mock_title_file_filament_type")
    assert state is not None
    assert state.state == "PETG"

    state = hass.states.get("sensor.workshop_mock_title_estimated_printing_time")
    assert state is not None
    assert state.state == "3811"

    get_file_metadata.assert_not_called()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_file_metadata_sensors_unavailable_when_download_times_out(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: None,
    mock_get_status_printing: dict[str, Any],
    mock_job_api_printing: dict[str, Any],
) -> None:
    """Test print file metadata timeout does not block integration setup."""
    with patch("pyprusalink.PrusaLink.get_file_metadata", side_effect=TimeoutError):
        assert await async_setup_component(hass, DOMAIN, {})

    state = hass.states.get("sensor.workshop_mock_title_filament_used_weight")
    assert state is not None
    assert state.state == "unavailable"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_axis_x_y_sensors(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: None
) -> None:
    """Test X and Y axis position sensors."""
    assert await async_setup_component(hass, DOMAIN, {})

    state = hass.states.get("sensor.workshop_mock_title_x_position")
    assert state is not None
    assert state.state == "7.9"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfLength.MILLIMETERS
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.DISTANCE
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT

    state = hass.states.get("sensor.workshop_mock_title_y_position")
    assert state is not None
    assert state.state == "8.4"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfLength.MILLIMETERS
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.DISTANCE
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_axis_x_y_not_created_when_absent(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: None,
    mock_get_status_idle: dict[str, Any],
) -> None:
    """X and Y sensors are not created when axis fields are absent from the response."""
    del mock_get_status_idle["printer"]["axis_x"]
    del mock_get_status_idle["printer"]["axis_y"]
    assert await async_setup_component(hass, DOMAIN, {})

    assert hass.states.get("sensor.workshop_mock_title_x_position") is None
    assert hass.states.get("sensor.workshop_mock_title_y_position") is None


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_min_extrusion_temp_sensor(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: None
) -> None:
    """Test minimum extrusion temperature sensor from info endpoint."""
    assert await async_setup_component(hass, DOMAIN, {})

    state = hass.states.get("sensor.workshop_mock_title_minimum_extrusion_temperature")
    assert state is not None
    assert state.state == "170"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TEMPERATURE
    assert ATTR_STATE_CLASS not in state.attributes


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_min_extrusion_temp_not_created_when_absent(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: None,
    mock_info_api: dict[str, Any],
) -> None:
    """Min extrusion temp sensor is not created when the info field is absent."""
    del mock_info_api["min_extrusion_temp"]
    assert await async_setup_component(hass, DOMAIN, {})

    assert (
        hass.states.get("sensor.workshop_mock_title_minimum_extrusion_temperature")
        is None
    )
