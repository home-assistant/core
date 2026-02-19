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
async def test_min_sensors_v1_api(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_growatt_v1_api,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test MIN device sensor entities with V1 API."""
    # V1 API only supports MIN devices (type 7)
    mock_growatt_v1_api.device_list.return_value = {
        "devices": [{"device_sn": "MIN123456", "type": 7}]
    }

    with patch("homeassistant.components.growatt_server.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("device_type", "device_sn"),
    [
        ("tlx", "TLX123456"),
        ("inverter", "INV123456"),
        ("storage", "STO123456"),
        ("mix", "MIX123456"),
    ],
    ids=["tlx", "inverter", "storage", "mix"],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.freeze_time("2023-10-21")
async def test_sensors_classic_api(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_growatt_classic_api,
    mock_config_entry_classic: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_type: str,
    device_sn: str,
) -> None:
    """Test sensor entities for non-MIN device types with Classic API."""
    # Classic API supports all device types
    mock_growatt_classic_api.device_list.return_value = [
        {"deviceSn": device_sn, "deviceType": device_type}
    ]
    # Device detail methods (inverter_detail, storage_detail, mix_detail, tlx_detail)
    # are already configured in the default mock_growatt_classic_api fixture

    with patch("homeassistant.components.growatt_server.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry_classic)

    await snapshot_platform(
        hass, entity_registry, snapshot, mock_config_entry_classic.entry_id
    )


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


async def test_midnight_bounce_suppression(
    hass: HomeAssistant,
    mock_growatt_v1_api,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that stale yesterday values after midnight reset are suppressed.

    The Growatt API sometimes delivers stale yesterday values after a midnight
    reset (9.5 → 0 → 9.5 → 0), causing TOTAL_INCREASING double-counting.
    """
    with patch("homeassistant.components.growatt_server.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    entity_id = "sensor.test_plant_total_energy_today"

    # Initial state: 12.5 kWh produced today
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "12.5"

    # Step 1: Midnight reset — API returns 0 (legitimate reset)
    mock_growatt_v1_api.plant_energy_overview.return_value = {
        "today_energy": 0,
        "total_energy": 1250.0,
        "current_power": 0,
    }
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "0"

    # Step 2: Stale bounce — API returns yesterday's value (12.5) after reset
    mock_growatt_v1_api.plant_energy_overview.return_value = {
        "today_energy": 12.5,
        "total_energy": 1250.0,
        "current_power": 0,
    }
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Bounce should be suppressed — state stays at 0
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "0"

    # Step 3: Another reset arrives — still 0 (no double-counting)
    mock_growatt_v1_api.plant_energy_overview.return_value = {
        "today_energy": 0,
        "total_energy": 1250.0,
        "current_power": 0,
    }
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "0"

    # Step 4: Genuine new production — small value passes through
    mock_growatt_v1_api.plant_energy_overview.return_value = {
        "today_energy": 0.1,
        "total_energy": 1250.1,
        "current_power": 500,
    }
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "0.1"


async def test_normal_reset_no_bounce(
    hass: HomeAssistant,
    mock_growatt_v1_api,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that normal midnight reset without bounce passes through correctly."""
    with patch("homeassistant.components.growatt_server.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    entity_id = "sensor.test_plant_total_energy_today"

    # Initial state: 9.5 kWh
    mock_growatt_v1_api.plant_energy_overview.return_value = {
        "today_energy": 9.5,
        "total_energy": 1250.0,
        "current_power": 0,
    }
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "9.5"

    # Midnight reset — API returns 0
    mock_growatt_v1_api.plant_energy_overview.return_value = {
        "today_energy": 0,
        "total_energy": 1250.0,
        "current_power": 0,
    }
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "0"

    # No bounce — genuine new production starts
    mock_growatt_v1_api.plant_energy_overview.return_value = {
        "today_energy": 0.1,
        "total_energy": 1250.1,
        "current_power": 500,
    }
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "0.1"

    # Production continues normally
    mock_growatt_v1_api.plant_energy_overview.return_value = {
        "today_energy": 1.5,
        "total_energy": 1251.5,
        "current_power": 2000,
    }
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "1.5"


async def test_midnight_bounce_repeated(
    hass: HomeAssistant,
    mock_growatt_v1_api,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test multiple consecutive stale bounces are all suppressed."""
    with patch("homeassistant.components.growatt_server.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    entity_id = "sensor.test_plant_total_energy_today"

    # Set up a known pre-reset value
    mock_growatt_v1_api.plant_energy_overview.return_value = {
        "today_energy": 8.0,
        "total_energy": 1250.0,
        "current_power": 0,
    }
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(entity_id).state == "8.0"

    # Midnight reset
    mock_growatt_v1_api.plant_energy_overview.return_value = {
        "today_energy": 0,
        "total_energy": 1250.0,
        "current_power": 0,
    }
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(entity_id).state == "0"

    # First stale bounce — suppressed
    mock_growatt_v1_api.plant_energy_overview.return_value = {
        "today_energy": 8.0,
        "total_energy": 1250.0,
        "current_power": 0,
    }
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(entity_id).state == "0"

    # Back to 0
    mock_growatt_v1_api.plant_energy_overview.return_value = {
        "today_energy": 0,
        "total_energy": 1250.0,
        "current_power": 0,
    }
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(entity_id).state == "0"

    # Second stale bounce — also suppressed
    mock_growatt_v1_api.plant_energy_overview.return_value = {
        "today_energy": 8.0,
        "total_energy": 1250.0,
        "current_power": 0,
    }
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(entity_id).state == "0"

    # Back to 0 again
    mock_growatt_v1_api.plant_energy_overview.return_value = {
        "today_energy": 0,
        "total_energy": 1250.0,
        "current_power": 0,
    }
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(entity_id).state == "0"

    # Finally, genuine new production passes through
    mock_growatt_v1_api.plant_energy_overview.return_value = {
        "today_energy": 0.2,
        "total_energy": 1250.2,
        "current_power": 1000,
    }
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(entity_id).state == "0.2"


async def test_non_total_increasing_sensor_unaffected_by_bounce_suppression(
    hass: HomeAssistant,
    mock_growatt_v1_api,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that non-TOTAL_INCREASING sensors are not affected by bounce suppression.

    The total_energy_output sensor (totalEnergy) has state_class=TOTAL,
    so bounce suppression (which only targets TOTAL_INCREASING) should not apply.
    """
    with patch("homeassistant.components.growatt_server.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    # total_energy_output uses state_class=TOTAL (not TOTAL_INCREASING)
    entity_id = "sensor.test_plant_total_lifetime_energy_output"

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "1250.0"

    # Simulate API returning 0 — no bounce suppression on TOTAL sensors
    mock_growatt_v1_api.plant_energy_overview.return_value = {
        "today_energy": 12.5,
        "total_energy": 0,
        "current_power": 2500,
    }
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "0"

    # Value recovers — passes through without suppression
    mock_growatt_v1_api.plant_energy_overview.return_value = {
        "today_energy": 12.5,
        "total_energy": 1250.0,
        "current_power": 2500,
    }
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "1250.0"


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
