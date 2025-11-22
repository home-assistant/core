"""Tests for the Growatt Server sensor platform."""

from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import growattServer
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_sensors(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_growatt_v1_api,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all sensor entities with snapshot."""
    with patch("homeassistant.components.growatt_server.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_sensor_coordinator_updates(
    hass: HomeAssistant,
    mock_growatt_v1_api,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensors update when coordinator refreshes."""
    with patch("homeassistant.components.growatt_server.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    # Verify sensor exists
    state = hass.states.get("sensor.test_plant_total_energy_today")
    assert state is not None
    assert state.state == "12.5"

    # Update mock data
    mock_growatt_v1_api.plant_energy_overview.return_value = {
        "today_energy": 25.0,  # Changed from 12.5
        "total_energy": 1250.0,
        "current_power": 2500,
    }

    # Trigger coordinator refresh
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Verify state updated
    state = hass.states.get("sensor.test_plant_total_energy_today")
    assert state is not None
    assert state.state == "25.0"


async def test_sensor_unavailable_on_coordinator_error(
    hass: HomeAssistant,
    mock_growatt_v1_api,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensors become unavailable when coordinator fails."""
    with patch("homeassistant.components.growatt_server.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    # Verify sensor is initially available
    state = hass.states.get("sensor.min123456_all_batteries_charged_today")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE

    # Cause coordinator update to fail
    mock_growatt_v1_api.min_detail.side_effect = growattServer.GrowattV1ApiError(
        "Connection timeout"
    )

    # Trigger coordinator refresh
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Verify sensor becomes unavailable
    state = hass.states.get("sensor.min123456_all_batteries_charged_today")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_total_sensors_classic_api(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_growatt_classic_api,
    mock_config_entry_classic: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test total sensors with Classic API."""
    # Classic API uses TLX devices
    mock_growatt_classic_api.device_list.return_value = [
        {"deviceSn": "TLX123456", "deviceType": "tlx"}
    ]

    with patch("homeassistant.components.growatt_server.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry_classic)

    await snapshot_platform(
        hass, entity_registry, snapshot, mock_config_entry_classic.entry_id
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_entity_registry(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_growatt_v1_api,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sensor entities are properly registered."""
    with patch("homeassistant.components.growatt_server.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
