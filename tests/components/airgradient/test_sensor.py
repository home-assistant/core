"""Tests for the AirGradient sensor platform."""

from dataclasses import replace
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from airgradient import AirGradientError, ApiVersion
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import async_load_measures_fixture, setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    airgradient_devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.airgradient.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_create_entities(
    hass: HomeAssistant,
    mock_airgradient_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test creating entities."""
    mock_airgradient_client.get_current_measures.return_value = (
        await async_load_measures_fixture(hass, "measures_after_boot.json")
    )
    with patch("homeassistant.components.airgradient.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    assert len(hass.states.async_all()) == 0
    mock_airgradient_client.get_current_measures.return_value = (
        await async_load_measures_fixture(hass, "current_measures_indoor.json")
    )
    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 9


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_v1_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_v1_airgradient_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test V1 sensor entities."""
    with patch("homeassistant.components.airgradient.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_v1_sensor_defaults(
    hass: HomeAssistant,
    mock_v1_airgradient_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test V1 sensor default enablement."""
    with patch("homeassistant.components.airgradient.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    battery_entry = entity_registry.async_get("sensor.airgradient_battery_percentage")
    assert battery_entry is not None
    assert battery_entry.disabled_by is None
    for entity_id in (
        "sensor.airgradient_pm0_5_particle_count",
        "sensor.airgradient_pm1_particle_count",
        "sensor.airgradient_pm2_5_particle_count",
        "sensor.airgradient_pm5_particle_count",
        "sensor.airgradient_pm10_particle_count",
        "sensor.airgradient_battery_voltage",
        "sensor.airgradient_input_voltage",
    ):
        entity_entry = entity_registry.async_get(entity_id)
        assert entity_entry is not None
        assert entity_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert hass.states.get("sensor.airgradient_raw_pm2_5") is None


async def test_v1_measurements_can_appear_later(
    hass: HomeAssistant,
    mock_v1_airgradient_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test omitted V1 measurements are added when they become available."""
    mock_v1_airgradient_client.get_current_measures.return_value = (
        await async_load_measures_fixture(
            hass, "measures_v1_minimal.json", ApiVersion.V1
        )
    )
    with patch("homeassistant.components.airgradient.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.airgradient_battery_percentage") is None
    mock_v1_airgradient_client.get_current_measures.return_value = replace(
        await async_load_measures_fixture(hass, "measures_v1_full.json", ApiVersion.V1),
        raw_pm02=2.5,
    )
    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    battery_state = hass.states.get("sensor.airgradient_battery_percentage")
    assert battery_state is not None
    assert battery_state.state == "87"


async def test_v1_zero_measurements(
    hass: HomeAssistant,
    mock_v1_airgradient_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test zero-valued V1 measurements are not treated as missing."""
    mock_v1_airgradient_client.get_current_measures.return_value = (
        await async_load_measures_fixture(hass, "measures_v1_zero.json", ApiVersion.V1)
    )
    with patch("homeassistant.components.airgradient.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    battery_state = hass.states.get("sensor.airgradient_battery_percentage")
    assert battery_state is not None
    assert battery_state.state == "0"


async def test_connection_error(
    hass: HomeAssistant,
    mock_airgradient_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test connection error."""
    await setup_integration(hass, mock_config_entry)

    mock_airgradient_client.get_current_measures.side_effect = AirGradientError()
    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.airgradient_humidity").state == STATE_UNAVAILABLE
