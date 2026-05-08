"""Tests for iZone climate platform."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant import config_entries
from homeassistant.components.climate import ClimateEntityFeature
from homeassistant.components.izone.const import UNAVAILABLE_DEBOUNCE
from homeassistant.core import HomeAssistant
import homeassistant.helpers.entity_registry as er

from . import get_discovery_service, setup_controller, setup_integration
from .conftest import create_mock_controller, create_mock_zone

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


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


async def test_disconnect_debounce_stays_available(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_discovery: AsyncMock,
    mock_controller: AsyncMock,
) -> None:
    """Test that a transient disconnect does not immediately mark entity unavailable."""
    await setup_integration(hass, mock_config_entry)
    await setup_controller(hass, mock_discovery, mock_controller)

    entity_id = "climate.izone_controller_test_controller_123"
    entity = hass.states.get(entity_id)
    assert entity is not None
    assert entity.state != "unavailable"

    # Simulate a disconnect
    disco = get_discovery_service(mock_discovery)
    disco.controller_disconnected(mock_controller, ConnectionError("timeout"))
    await hass.async_block_till_done()

    # Entity should still be available (debounce grace period)
    entity = hass.states.get(entity_id)
    assert entity.state != "unavailable"


async def test_disconnect_debounce_becomes_unavailable_after_timeout(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_discovery: AsyncMock,
    mock_controller: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that entity becomes unavailable after the debounce period expires."""
    await setup_integration(hass, mock_config_entry)
    await setup_controller(hass, mock_discovery, mock_controller)

    entity_id = "climate.izone_controller_test_controller_123"

    # Simulate a disconnect
    disco = get_discovery_service(mock_discovery)
    disco.controller_disconnected(mock_controller, ConnectionError("timeout"))
    await hass.async_block_till_done()

    # Still available during debounce
    entity = hass.states.get(entity_id)
    assert entity.state != "unavailable"

    # Advance past the debounce period
    freezer.tick(timedelta(seconds=UNAVAILABLE_DEBOUNCE + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Now it should be unavailable
    entity = hass.states.get(entity_id)
    assert entity.state == "unavailable"


async def test_disconnect_debounce_cancelled_by_reconnect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_discovery: AsyncMock,
    mock_controller: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that reconnecting during debounce cancels the unavailable timer."""
    await setup_integration(hass, mock_config_entry)
    await setup_controller(hass, mock_discovery, mock_controller)

    entity_id = "climate.izone_controller_test_controller_123"

    disco = get_discovery_service(mock_discovery)

    # Simulate disconnect
    disco.controller_disconnected(mock_controller, ConnectionError("timeout"))
    await hass.async_block_till_done()

    # Advance partway through debounce
    freezer.tick(timedelta(seconds=UNAVAILABLE_DEBOUNCE // 2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Still available
    entity = hass.states.get(entity_id)
    assert entity.state != "unavailable"

    # Simulate reconnect (cancels debounce timer)
    disco.controller_reconnected(mock_controller)
    await hass.async_block_till_done()

    # Advance past the original debounce period
    freezer.tick(timedelta(seconds=UNAVAILABLE_DEBOUNCE))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Should still be available (timer was cancelled)
    entity = hass.states.get(entity_id)
    assert entity.state != "unavailable"


async def test_disconnect_reconnect_flapping(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_discovery: AsyncMock,
    mock_controller: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that rapid disconnect/reconnect cycles don't cause unavailability."""
    await setup_integration(hass, mock_config_entry)
    await setup_controller(hass, mock_discovery, mock_controller)

    entity_id = "climate.izone_controller_test_controller_123"
    disco = get_discovery_service(mock_discovery)

    # Simulate 5 rapid disconnect/reconnect cycles (like the real issue)
    for _ in range(5):
        disco.controller_disconnected(mock_controller, ConnectionError("timeout"))
        await hass.async_block_till_done()

        # Advance 30 seconds (simulating keepalive reconnect)
        freezer.tick(timedelta(seconds=30))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        disco.controller_reconnected(mock_controller)
        await hass.async_block_till_done()

    # Entity should never have gone unavailable
    entity = hass.states.get(entity_id)
    assert entity.state != "unavailable"


async def test_zone_follows_controller_debounced_availability(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_discovery: AsyncMock,
    mock_controller: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that zones follow the controller's debounced availability."""
    await setup_integration(hass, mock_config_entry)
    await setup_controller(hass, mock_discovery, mock_controller)

    zone_entity_id = "climate.living_room"
    disco = get_discovery_service(mock_discovery)

    # Simulate disconnect
    disco.controller_disconnected(mock_controller, ConnectionError("timeout"))
    await hass.async_block_till_done()

    # Zone should still be available during debounce
    zone = hass.states.get(zone_entity_id)
    assert zone is not None
    assert zone.state != "unavailable"

    # Advance past debounce
    freezer.tick(timedelta(seconds=UNAVAILABLE_DEBOUNCE + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Zone should now be unavailable (follows controller)
    zone = hass.states.get(zone_entity_id)
    assert zone.state == "unavailable"


async def test_debounce_cancelled_on_entity_removal(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_discovery: AsyncMock,
    mock_controller: AsyncMock,
) -> None:
    """Test that the debounce timer is cancelled when entity is removed."""
    await setup_integration(hass, mock_config_entry)
    await setup_controller(hass, mock_discovery, mock_controller)

    disco = get_discovery_service(mock_discovery)

    # Trigger a disconnect to start the debounce timer
    disco.controller_disconnected(mock_controller, ConnectionError("timeout"))
    await hass.async_block_till_done()

    # Unload the entry — should cancel debounce without error
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify the entry is unloaded (no crash from stale callback)
    assert mock_config_entry.state is config_entries.ConfigEntryState.NOT_LOADED
