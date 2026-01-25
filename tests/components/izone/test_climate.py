"""Tests for iZone climate platform."""

from collections.abc import Awaitable, Callable
from unittest.mock import Mock

from homeassistant.components.climate import ClimateEntityFeature
from homeassistant.core import HomeAssistant

from .conftest import create_mock_controller, create_mock_zone

from tests.common import MockConfigEntry


async def test_basic_controller_properties(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pizone_discovery_service: Mock,
    setup_integration: Callable[[MockConfigEntry, Mock], Awaitable[Mock]],
) -> None:
    """Test basic properties of ControllerDevice."""
    zone = create_mock_zone(index=0, name="Living Room")
    controller = create_mock_controller(
        device_uid="test_controller_123",
        ras_mode="master",
        zone_ctrl=1,
        zones_total=1,
        zones=[zone],
    )
    mock_pizone_discovery_service.controllers = {"test_controller_123": controller}

    await setup_integration(mock_config_entry, mock_pizone_discovery_service)

    entity_id = "climate.izone_controller_test_controller_123"
    entity = hass.states.get(entity_id)

    assert entity is not None
    # Verify basic entity properties via state machine
    assert entity.attributes.get("friendly_name") is not None
    # Device info can't be directly accessed via state machine,
    # but we can verify the entity exists and has the expected entity_id
    assert entity.entity_id == entity_id


async def test_target_temperature_feature_ras_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pizone_discovery_service: Mock,
    setup_integration: Callable[[MockConfigEntry, Mock], Awaitable[Mock]],
) -> None:
    """Test TARGET_TEMPERATURE feature enabled in RAS mode."""
    # Scenario 1: Controller in RAS mode
    zone = create_mock_zone(index=0, name="Living Room")
    controller = create_mock_controller(
        device_uid="test_controller_123",
        ras_mode="RAS",
        zones=[zone],
    )
    mock_pizone_discovery_service.controllers = {"test_controller_123": controller}

    await setup_integration(mock_config_entry, mock_pizone_discovery_service)

    entity_id = "climate.izone_controller_test_controller_123"
    entity = hass.states.get(entity_id)

    assert entity is not None
    assert (
        entity.attributes["supported_features"]
        & ClimateEntityFeature.TARGET_TEMPERATURE
    ) == ClimateEntityFeature.TARGET_TEMPERATURE


async def test_target_temperature_feature_master_mode_invalid_zone(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pizone_discovery_service: Mock,
    setup_integration: Callable[[MockConfigEntry, Mock], Awaitable[Mock]],
) -> None:
    """Test TARGET_TEMPERATURE feature enabled when control zone is invalid."""
    # Scenario 2: Controller in master mode with control zone > zones_total
    zone = create_mock_zone(index=0, name="Living Room")
    controller = create_mock_controller(
        device_uid="test_controller_123",
        ras_mode="master",
        zone_ctrl=13,  # Greater than zones_total (4)
        zones_total=4,
        zones=[zone],
    )
    mock_pizone_discovery_service.controllers = {"test_controller_123": controller}

    await setup_integration(mock_config_entry, mock_pizone_discovery_service)

    entity_id = "climate.izone_controller_test_controller_123"
    entity = hass.states.get(entity_id)

    assert entity is not None
    assert (
        entity.attributes["supported_features"]
        & ClimateEntityFeature.TARGET_TEMPERATURE
    ) == ClimateEntityFeature.TARGET_TEMPERATURE


async def test_target_temperature_feature_zone_without_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pizone_discovery_service: Mock,
    setup_integration: Callable[[MockConfigEntry, Mock], Awaitable[Mock]],
) -> None:
    """Test TARGET_TEMPERATURE feature enabled when any zone lacks temperature sensor."""
    # Scenario 3: At least one zone without temperature sensor
    zone_with_temp = create_mock_zone(index=0, name="Living Room", temp_current=22.5)
    zone_without_temp = create_mock_zone(
        index=1, name="Bedroom", temp_current=None
    )  # No sensor

    controller = create_mock_controller(
        device_uid="test_controller_123",
        ras_mode="master",
        zone_ctrl=1,  # Valid zone
        zones_total=2,
        zones=[zone_with_temp, zone_without_temp],
    )
    mock_pizone_discovery_service.controllers = {"test_controller_123": controller}

    await setup_integration(mock_config_entry, mock_pizone_discovery_service)

    entity_id = "climate.izone_controller_test_controller_123"
    entity = hass.states.get(entity_id)

    assert entity is not None
    assert (
        entity.attributes["supported_features"]
        & ClimateEntityFeature.TARGET_TEMPERATURE
    ) == ClimateEntityFeature.TARGET_TEMPERATURE


async def test_target_temperature_feature_not_enabled_normal_master(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pizone_discovery_service: Mock,
    setup_integration: Callable[[MockConfigEntry, Mock], Awaitable[Mock]],
) -> None:
    """Test TARGET_TEMPERATURE feature NOT enabled in normal master mode."""
    # Normal master mode with valid control zone and all zones have sensors
    zone = create_mock_zone(index=0, name="Living Room")
    controller = create_mock_controller(
        device_uid="test_controller_123",
        ras_mode="master",
        zone_ctrl=1,  # Valid zone (less than zones_total)
        zones_total=4,
        zones=[zone],  # All zones have temp sensors
    )
    mock_pizone_discovery_service.controllers = {"test_controller_123": controller}

    await setup_integration(mock_config_entry, mock_pizone_discovery_service)

    entity_id = "climate.izone_controller_test_controller_123"
    entity = hass.states.get(entity_id)

    assert entity is not None
    # Should NOT have TARGET_TEMPERATURE feature
    assert (
        entity.attributes["supported_features"]
        & ClimateEntityFeature.TARGET_TEMPERATURE
    ) != ClimateEntityFeature.TARGET_TEMPERATURE


async def test_target_temperature_feature_all_zones_with_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pizone_discovery_service: Mock,
    setup_integration: Callable[[MockConfigEntry, Mock], Awaitable[Mock]],
) -> None:
    """Test TARGET_TEMPERATURE feature NOT enabled when all zones have sensors."""
    # Create multiple zones, all with temperature sensors
    zone1 = create_mock_zone(index=0, name="Zone 1", temp_current=22.5)
    zone2 = create_mock_zone(index=1, name="Zone 2", temp_current=23.0)
    zone3 = create_mock_zone(index=2, name="Zone 3", temp_current=21.5)

    controller = create_mock_controller(
        device_uid="test_controller_123",
        ras_mode="master",
        zone_ctrl=1,
        zones_total=3,
        zones=[zone1, zone2, zone3],
    )
    mock_pizone_discovery_service.controllers = {"test_controller_123": controller}

    await setup_integration(mock_config_entry, mock_pizone_discovery_service)

    entity_id = "climate.izone_controller_test_controller_123"
    entity = hass.states.get(entity_id)

    assert entity is not None
    # Should NOT have TARGET_TEMPERATURE feature
    assert (
        entity.attributes["supported_features"]
        & ClimateEntityFeature.TARGET_TEMPERATURE
    ) != ClimateEntityFeature.TARGET_TEMPERATURE


async def test_target_temperature_feature_multiple_zones_one_without_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pizone_discovery_service: Mock,
    setup_integration: Callable[[MockConfigEntry, Mock], Awaitable[Mock]],
) -> None:
    """Test TARGET_TEMPERATURE feature enabled with multiple zones when one lacks sensor."""
    # Create multiple zones, one without temperature sensor
    zone1 = create_mock_zone(index=0, name="Zone 1", temp_current=22.5)
    zone2 = create_mock_zone(index=1, name="Zone 2", temp_current=None)  # No sensor
    zone3 = create_mock_zone(index=2, name="Zone 3", temp_current=21.5)

    controller = create_mock_controller(
        device_uid="test_controller_123",
        ras_mode="master",
        zone_ctrl=1,
        zones_total=3,
        zones=[zone1, zone2, zone3],
    )
    mock_pizone_discovery_service.controllers = {"test_controller_123": controller}

    await setup_integration(mock_config_entry, mock_pizone_discovery_service)

    entity_id = "climate.izone_controller_test_controller_123"
    entity = hass.states.get(entity_id)

    assert entity is not None
    assert (
        entity.attributes["supported_features"]
        & ClimateEntityFeature.TARGET_TEMPERATURE
    ) == ClimateEntityFeature.TARGET_TEMPERATURE


async def test_target_temperature_feature_slave_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pizone_discovery_service: Mock,
    setup_integration: Callable[[MockConfigEntry, Mock], Awaitable[Mock]],
) -> None:
    """Test TARGET_TEMPERATURE feature NOT enabled in slave mode."""
    # Slave mode should not enable TARGET_TEMPERATURE
    zone = create_mock_zone(index=0, name="Living Room")
    controller = create_mock_controller(
        device_uid="test_controller_123",
        ras_mode="slave",
        zone_ctrl=1,
        zones_total=4,
        zones=[zone],
    )
    mock_pizone_discovery_service.controllers = {"test_controller_123": controller}

    await setup_integration(mock_config_entry, mock_pizone_discovery_service)

    entity_id = "climate.izone_controller_test_controller_123"
    entity = hass.states.get(entity_id)

    assert entity is not None
    # Should NOT have TARGET_TEMPERATURE feature
    assert (
        entity.attributes["supported_features"]
        & ClimateEntityFeature.TARGET_TEMPERATURE
    ) != ClimateEntityFeature.TARGET_TEMPERATURE


async def test_target_temperature_feature_master_mode_zone_13(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pizone_discovery_service: Mock,
    setup_integration: Callable[[MockConfigEntry, Mock], Awaitable[Mock]],
) -> None:
    """Test TARGET_TEMPERATURE feature enabled when control zone is 13 (master unit)."""
    # Master mode with zone_ctrl = 13 (the master unit itself)
    zone = create_mock_zone(index=0, name="Living Room")
    controller = create_mock_controller(
        device_uid="test_controller_123",
        ras_mode="master",
        zone_ctrl=13,
        zones_total=4,
        zones=[zone],
    )
    mock_pizone_discovery_service.controllers = {"test_controller_123": controller}

    await setup_integration(mock_config_entry, mock_pizone_discovery_service)

    entity_id = "climate.izone_controller_test_controller_123"
    entity = hass.states.get(entity_id)

    assert entity is not None
    assert (
        entity.attributes["supported_features"]
        & ClimateEntityFeature.TARGET_TEMPERATURE
    ) == ClimateEntityFeature.TARGET_TEMPERATURE
