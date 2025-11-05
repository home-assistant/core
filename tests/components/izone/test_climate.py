"""Tests for iZone climate platform."""

from unittest.mock import Mock

from pizone import Controller, Zone
import pytest

from homeassistant.components.climate import ClimateEntityFeature
from homeassistant.components.izone.climate import ControllerDevice
from homeassistant.components.izone.const import IZONE


@pytest.fixture
def mock_controller() -> Mock:
    """Create a mock Controller."""
    controller = Mock(spec=Controller)
    controller.device_uid = "test_controller_123"
    controller.sys_type = "iZone310"
    controller.zones_total = 4
    controller.zone_ctrl = 1
    controller.ras_mode = "master"
    controller.free_air_enabled = False
    controller.free_air = False
    controller.is_on = True
    controller.mode = Controller.Mode.COOL
    controller.temp_setpoint = 24.0
    controller.temp_return = 22.0
    controller.fan_modes = [
        Controller.Fan.LOW,
        Controller.Fan.MED,
        Controller.Fan.HIGH,
        Controller.Fan.AUTO,
    ]
    return controller


@pytest.fixture
def mock_zone_with_temp() -> Mock:
    """Create a mock Zone with temperature sensor."""
    zone = Mock(spec=Zone)
    zone.index = 0
    zone.name = "Living Room"
    zone.type = Zone.Type.AUTO
    zone.mode = Zone.Mode.AUTO
    zone.temp_current = 22.5
    zone.temp_setpoint = 24.0
    zone.airflow_min = 0
    zone.airflow_max = 100
    return zone


@pytest.fixture
def mock_zone_without_temp() -> Mock:
    """Create a mock Zone without temperature sensor."""
    zone = Mock(spec=Zone)
    zone.index = 1
    zone.name = "Bedroom"
    zone.type = Zone.Type.AUTO
    zone.mode = Zone.Mode.AUTO
    zone.temp_current = None  # No temperature sensor
    zone.temp_setpoint = 24.0
    zone.airflow_min = 0
    zone.airflow_max = 100
    return zone


async def test_target_temperature_feature_ras_mode(
    mock_controller: Mock,
    mock_zone_with_temp: Mock,
) -> None:
    """Test TARGET_TEMPERATURE feature enabled in RAS mode."""
    # Scenario 1: Controller in RAS mode
    mock_controller.ras_mode = "RAS"
    mock_controller.zones = [mock_zone_with_temp]

    device = ControllerDevice(mock_controller)

    assert (
        device.supported_features & ClimateEntityFeature.TARGET_TEMPERATURE
    ) == ClimateEntityFeature.TARGET_TEMPERATURE


async def test_target_temperature_feature_master_mode_invalid_zone(
    mock_controller: Mock,
    mock_zone_with_temp: Mock,
) -> None:
    """Test TARGET_TEMPERATURE feature enabled when control zone is invalid."""
    # Scenario 2: Controller in master mode with control zone > zones_total
    mock_controller.ras_mode = "master"
    mock_controller.zone_ctrl = 13  # Greater than zones_total (4)
    mock_controller.zones_total = 4
    mock_controller.zones = [mock_zone_with_temp]

    device = ControllerDevice(mock_controller)

    assert (
        device.supported_features & ClimateEntityFeature.TARGET_TEMPERATURE
    ) == ClimateEntityFeature.TARGET_TEMPERATURE


async def test_target_temperature_feature_zone_without_sensor(
    mock_controller: Mock,
    mock_zone_with_temp: Mock,
    mock_zone_without_temp: Mock,
) -> None:
    """Test TARGET_TEMPERATURE feature enabled when any zone lacks temperature sensor."""
    # Scenario 3: At least one zone without temperature sensor
    mock_controller.ras_mode = "master"
    mock_controller.zone_ctrl = 1  # Valid zone
    mock_controller.zones_total = 2
    mock_controller.zones = [
        mock_zone_with_temp,
        mock_zone_without_temp,  # This zone has no temp sensor
    ]

    device = ControllerDevice(mock_controller)

    assert (
        device.supported_features & ClimateEntityFeature.TARGET_TEMPERATURE
    ) == ClimateEntityFeature.TARGET_TEMPERATURE


async def test_target_temperature_feature_not_enabled_normal_master(
    mock_controller: Mock,
    mock_zone_with_temp: Mock,
) -> None:
    """Test TARGET_TEMPERATURE feature NOT enabled in normal master mode."""
    # Normal master mode with valid control zone and all zones have sensors
    mock_controller.ras_mode = "master"
    mock_controller.zone_ctrl = 1  # Valid zone (less than zones_total)
    mock_controller.zones_total = 4
    mock_controller.zones = [mock_zone_with_temp]  # All zones have temp sensors

    device = ControllerDevice(mock_controller)

    # Should NOT have TARGET_TEMPERATURE feature
    assert (
        device.supported_features & ClimateEntityFeature.TARGET_TEMPERATURE
    ) != ClimateEntityFeature.TARGET_TEMPERATURE


async def test_target_temperature_feature_all_zones_with_sensors(
    mock_controller: Mock,
) -> None:
    """Test TARGET_TEMPERATURE feature NOT enabled when all zones have sensors."""
    # Create multiple zones, all with temperature sensors
    zone1 = Mock(spec=Zone)
    zone1.index = 0
    zone1.type = Zone.Type.AUTO
    zone1.mode = Zone.Mode.AUTO
    zone1.temp_current = 22.5
    zone1.airflow_min = 0
    zone1.airflow_max = 100
    zone2 = Mock(spec=Zone)
    zone2.index = 1
    zone2.type = Zone.Type.AUTO
    zone2.mode = Zone.Mode.AUTO
    zone2.temp_current = 23.0
    zone2.airflow_min = 0
    zone2.airflow_max = 100
    zone3 = Mock(spec=Zone)
    zone3.index = 2
    zone3.type = Zone.Type.AUTO
    zone3.mode = Zone.Mode.AUTO
    zone3.temp_current = 21.5
    zone3.airflow_min = 0
    zone3.airflow_max = 100

    mock_controller.ras_mode = "master"
    mock_controller.zone_ctrl = 1
    mock_controller.zones_total = 3
    mock_controller.zones = [zone1, zone2, zone3]

    device = ControllerDevice(mock_controller)

    # Should NOT have TARGET_TEMPERATURE feature
    assert (
        device.supported_features & ClimateEntityFeature.TARGET_TEMPERATURE
    ) != ClimateEntityFeature.TARGET_TEMPERATURE


async def test_target_temperature_feature_multiple_zones_one_without_sensor(
    mock_controller: Mock,
) -> None:
    """Test TARGET_TEMPERATURE feature enabled with multiple zones when one lacks sensor."""
    # Create multiple zones, one without temperature sensor
    zone1 = Mock(spec=Zone)
    zone1.index = 0
    zone1.type = Zone.Type.AUTO
    zone1.mode = Zone.Mode.AUTO
    zone1.temp_current = 22.5
    zone1.airflow_min = 0
    zone1.airflow_max = 100
    zone2 = Mock(spec=Zone)
    zone2.index = 1
    zone2.type = Zone.Type.AUTO
    zone2.mode = Zone.Mode.AUTO
    zone2.temp_current = None  # No sensor
    zone2.airflow_min = 0
    zone2.airflow_max = 100
    zone3 = Mock(spec=Zone)
    zone3.index = 2
    zone3.type = Zone.Type.AUTO
    zone3.mode = Zone.Mode.AUTO
    zone3.temp_current = 21.5
    zone3.airflow_min = 0
    zone3.airflow_max = 100

    mock_controller.ras_mode = "master"
    mock_controller.zone_ctrl = 1
    mock_controller.zones_total = 3
    mock_controller.zones = [zone1, zone2, zone3]

    device = ControllerDevice(mock_controller)

    assert (
        device.supported_features & ClimateEntityFeature.TARGET_TEMPERATURE
    ) == ClimateEntityFeature.TARGET_TEMPERATURE


async def test_target_temperature_feature_slave_mode(
    mock_controller: Mock,
    mock_zone_with_temp: Mock,
) -> None:
    """Test TARGET_TEMPERATURE feature NOT enabled in slave mode."""
    # Slave mode should not enable TARGET_TEMPERATURE
    mock_controller.ras_mode = "slave"
    mock_controller.zone_ctrl = 1
    mock_controller.zones_total = 4
    mock_controller.zones = [mock_zone_with_temp]

    device = ControllerDevice(mock_controller)

    # Should NOT have TARGET_TEMPERATURE feature
    assert (
        device.supported_features & ClimateEntityFeature.TARGET_TEMPERATURE
    ) != ClimateEntityFeature.TARGET_TEMPERATURE


async def test_target_temperature_feature_master_mode_zone_13(
    mock_controller: Mock,
    mock_zone_with_temp: Mock,
) -> None:
    """Test TARGET_TEMPERATURE feature enabled when control zone is 13 (master unit)."""
    # Master mode with zone_ctrl = 13 (the master unit itself)
    mock_controller.ras_mode = "master"
    mock_controller.zone_ctrl = 13
    mock_controller.zones_total = 4
    mock_controller.zones = [mock_zone_with_temp]

    device = ControllerDevice(mock_controller)

    assert (
        device.supported_features & ClimateEntityFeature.TARGET_TEMPERATURE
    ) == ClimateEntityFeature.TARGET_TEMPERATURE


async def test_basic_controller_properties(
    mock_controller: Mock,
    mock_zone_with_temp: Mock,
) -> None:
    """Test basic properties of ControllerDevice."""
    mock_controller.ras_mode = "master"
    mock_controller.zone_ctrl = 1
    mock_controller.zones_total = 1
    mock_controller.zones = [mock_zone_with_temp]

    device = ControllerDevice(mock_controller)

    assert device.unique_id == "test_controller_123"
    assert device.name is None  # Should be None with has_entity_name
    assert device._attr_has_entity_name is True
    assert device.device_info is not None
    assert (IZONE, "test_controller_123") in device.device_info["identifiers"]
