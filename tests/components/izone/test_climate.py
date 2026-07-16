"""Tests for iZone climate platform."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import ClimateEntityFeature
from homeassistant.core import HomeAssistant
import homeassistant.helpers.device_registry as dr
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

    entity_id = "climate.izone_controller_000000001"
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

    entity_id = "climate.izone_controller_000000001"
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

    entity_id = "climate.izone_controller_000000001"
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
    """Test TARGET_TEMPERATURE enabled when zone lacks temp sensor."""
    await setup_integration(hass, mock_config_entry)
    await setup_controller(hass, mock_discovery, mock_controller)

    entity_id = "climate.izone_controller_000000001"
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

    entity_id = "climate.izone_controller_000000001"
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
    """Test TARGET_TEMPERATURE enabled with multiple zones, one no sensor."""
    await setup_integration(hass, mock_config_entry)
    await setup_controller(hass, mock_discovery, mock_controller)

    entity_id = "climate.izone_controller_000000001"
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

    entity_id = "climate.izone_controller_000000001"
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

    entity_id = "climate.izone_controller_000000001"
    entity = hass.states.get(entity_id)

    assert entity is not None
    assert (
        entity.attributes["supported_features"]
        & ClimateEntityFeature.TARGET_TEMPERATURE
    ) == ClimateEntityFeature.TARGET_TEMPERATURE


async def test_setup_entry_only_adds_entities_for_matching_config_entry(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a config entry only adds entities for its matching controller."""
    matching_controller = create_mock_controller(
        device_uid="000000001", device_ip="192.0.2.1", zones_total=1
    )
    matching_controller.zones = [create_mock_zone(index=0, name="Living Room")]

    other_controller = create_mock_controller(
        device_uid="000000002", device_ip="192.0.2.2", zones_total=1
    )
    other_controller.zones = [create_mock_zone(index=0, name="Bedroom")]

    entry = MockConfigEntry(
        domain="izone",
        title="iZone",
        data={},
        unique_id="000000001",
        entry_id="test_entry_id",
        version=2,
    )

    with patch(
        "homeassistant.components.izone.discovery.pizone.discovery", autospec=True
    ) as mock_disco:
        mock_disco.return_value.start_discovery = AsyncMock()
        mock_disco.return_value.close = AsyncMock()
        mock_disco.return_value.fetch_controller = AsyncMock(
            return_value=matching_controller
        )
        mock_disco.return_value.fetch_controllers = AsyncMock(
            return_value={
                matching_controller.device_uid: matching_controller,
                other_controller.device_uid: other_controller,
            }
        )

        await setup_integration(hass, entry)

    entry_entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    unique_ids = {entity.unique_id for entity in entry_entities}

    assert unique_ids == {"000000001", "000000001_z1"}


@pytest.mark.parametrize("mock_zones", [[]])
@pytest.mark.parametrize(
    "mock_controller",
    [
        create_mock_controller(
            ras_mode="zones",
            sys_type="0",
            zones_total=0,
            free_air_enabled=False,
        )
    ],
)
async def test_controller_device_init_fault_bootstrap(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_discovery: AsyncMock,
    mock_controller: AsyncMock,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Controller climate entity is created with fault-shaped controller defaults."""
    await setup_integration(hass, mock_config_entry)
    await setup_controller(hass, mock_discovery, mock_controller)

    entity_id = "climate.izone_controller_000000001"
    assert hass.states.get(entity_id) is not None

    entry_entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert {entity.unique_id for entity in entry_entities} == {"000000001"}

    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None
    device_entry = device_registry.async_get(entity_entry.device_id)
    assert device_entry is not None
    assert device_entry.model == "0"
