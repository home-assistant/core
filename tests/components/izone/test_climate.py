"""Tests for iZone climate platform."""

from unittest.mock import AsyncMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import ClimateEntityFeature
from homeassistant.core import HomeAssistant
import homeassistant.helpers.entity_registry as er

from . import setup_controller, setup_integration
from .conftest import create_mock_controller, create_mock_zone

from tests.common import MockConfigEntry, snapshot_platform


async def test_basic_controller_properties(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_discovery: AsyncMock,
    mock_controller: AsyncMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test basic properties of ControllerDevice."""
    await setup_integration(hass, mock_config_entry)
    await setup_controller(hass, mock_discovery, mock_controller)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    entity_id = "climate.izone_controller_test_controller_123"
    entity = hass.states.get(entity_id)

    assert entity is not None
    assert (
        entity.attributes["supported_features"]
        & ClimateEntityFeature.TARGET_TEMPERATURE
    ) != ClimateEntityFeature.TARGET_TEMPERATURE


@pytest.mark.parametrize(
    "mock_controller",
    [
        create_mock_controller(
            ras_mode="RAS",
        )
    ],
)
async def test_target_temperature_feature_ras_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_discovery: AsyncMock,
    mock_controller: AsyncMock,
) -> None:
    """Test TARGET_TEMPERATURE feature enabled in RAS mode."""
    await setup_integration(hass, mock_config_entry)
    await setup_controller(hass, mock_discovery, mock_controller)

    entity_id = "climate.izone_controller_test_controller_123"
    entity = hass.states.get(entity_id)

    assert entity is not None
    assert (
        entity.attributes["supported_features"]
        & ClimateEntityFeature.TARGET_TEMPERATURE
    ) == ClimateEntityFeature.TARGET_TEMPERATURE


@pytest.mark.parametrize(
    "mock_controller",
    [
        create_mock_controller(
            zone_ctrl=13,  # Greater than zones_total (4)
            zones_total=4,
        )
    ],
)
async def test_target_temperature_feature_master_mode_invalid_zone(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_discovery: AsyncMock,
    mock_controller: AsyncMock,
) -> None:
    """Test TARGET_TEMPERATURE feature enabled when control zone is invalid."""
    await setup_integration(hass, mock_config_entry)
    await setup_controller(hass, mock_discovery, mock_controller)

    entity_id = "climate.izone_controller_test_controller_123"
    entity = hass.states.get(entity_id)

    assert entity is not None
    assert (
        entity.attributes["supported_features"]
        & ClimateEntityFeature.TARGET_TEMPERATURE
    ) == ClimateEntityFeature.TARGET_TEMPERATURE


@pytest.mark.parametrize(
    ("mock_controller", "mock_zones"),
    [
        (
            create_mock_controller(
                zone_ctrl=1,  # Valid zone
                zones_total=2,
            ),
            [
                create_mock_zone(index=0, name="Living Room", temp_current=22.5),
                create_mock_zone(
                    index=1, name="Bedroom", temp_current=None
                ),  # No sensor
            ],
        )
    ],
)
async def test_target_temperature_feature_zone_without_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_discovery: AsyncMock,
    mock_controller: AsyncMock,
) -> None:
    """Test TARGET_TEMPERATURE feature enabled when any zone lacks temperature sensor."""
    await setup_integration(hass, mock_config_entry)
    await setup_controller(hass, mock_discovery, mock_controller)

    entity_id = "climate.izone_controller_test_controller_123"
    entity = hass.states.get(entity_id)

    assert entity is not None
    assert (
        entity.attributes["supported_features"]
        & ClimateEntityFeature.TARGET_TEMPERATURE
    ) == ClimateEntityFeature.TARGET_TEMPERATURE


@pytest.mark.parametrize(
    ("mock_controller", "mock_zones"),
    [
        (
            create_mock_controller(
                zones_total=3,
            ),
            [
                create_mock_zone(index=0, name="Zone 1", temp_current=22.5),
                create_mock_zone(index=1, name="Zone 2", temp_current=23.0),
                create_mock_zone(index=2, name="Zone 3", temp_current=21.5),
            ],
        )
    ],
)
async def test_target_temperature_feature_all_zones_with_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_discovery: AsyncMock,
    mock_controller: AsyncMock,
) -> None:
    """Test TARGET_TEMPERATURE feature NOT enabled when all zones have sensors."""
    await setup_integration(hass, mock_config_entry)
    await setup_controller(hass, mock_discovery, mock_controller)

    entity_id = "climate.izone_controller_test_controller_123"
    entity = hass.states.get(entity_id)

    assert entity is not None
    # Should NOT have TARGET_TEMPERATURE feature
    assert (
        entity.attributes["supported_features"]
        & ClimateEntityFeature.TARGET_TEMPERATURE
    ) != ClimateEntityFeature.TARGET_TEMPERATURE


@pytest.mark.parametrize(
    ("mock_controller", "mock_zones"),
    [
        (
            create_mock_controller(
                zones_total=3,
            ),
            [
                create_mock_zone(index=0, name="Zone 1", temp_current=22.5),
                create_mock_zone(index=1, name="Zone 2", temp_current=None),
                create_mock_zone(index=2, name="Zone 3", temp_current=21.5),
            ],
        )
    ],
)
async def test_target_temperature_feature_multiple_zones_one_without_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_discovery: AsyncMock,
    mock_controller: AsyncMock,
) -> None:
    """Test TARGET_TEMPERATURE feature enabled with multiple zones when one lacks sensor."""
    await setup_integration(hass, mock_config_entry)
    await setup_controller(hass, mock_discovery, mock_controller)

    entity_id = "climate.izone_controller_test_controller_123"
    entity = hass.states.get(entity_id)

    assert entity is not None
    assert (
        entity.attributes["supported_features"]
        & ClimateEntityFeature.TARGET_TEMPERATURE
    ) == ClimateEntityFeature.TARGET_TEMPERATURE


@pytest.mark.parametrize(
    "mock_controller",
    [
        create_mock_controller(
            ras_mode="slave",
        )
    ],
)
async def test_target_temperature_feature_slave_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_discovery: AsyncMock,
    mock_controller: AsyncMock,
) -> None:
    """Test TARGET_TEMPERATURE feature NOT enabled in slave mode."""
    await setup_integration(hass, mock_config_entry)
    await setup_controller(hass, mock_discovery, mock_controller)

    entity_id = "climate.izone_controller_test_controller_123"
    entity = hass.states.get(entity_id)

    assert entity is not None
    # Should NOT have TARGET_TEMPERATURE feature
    assert (
        entity.attributes["supported_features"]
        & ClimateEntityFeature.TARGET_TEMPERATURE
    ) != ClimateEntityFeature.TARGET_TEMPERATURE


@pytest.mark.parametrize(
    "mock_controller",
    [
        create_mock_controller(
            zone_ctrl=13,
            zones_total=4,
        )
    ],
)
async def test_target_temperature_feature_master_mode_zone_13(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_discovery: AsyncMock,
    mock_controller: AsyncMock,
) -> None:
    """Test TARGET_TEMPERATURE feature enabled when control zone is 13 (master unit)."""
    await setup_integration(hass, mock_config_entry)
    await setup_controller(hass, mock_discovery, mock_controller)

    entity_id = "climate.izone_controller_test_controller_123"
    entity = hass.states.get(entity_id)

    assert entity is not None
    assert (
        entity.attributes["supported_features"]
        & ClimateEntityFeature.TARGET_TEMPERATURE
    ) == ClimateEntityFeature.TARGET_TEMPERATURE
