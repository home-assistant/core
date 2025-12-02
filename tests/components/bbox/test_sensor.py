"""Tests for Bbox sensor platform."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from aiobbox import BboxApiError, BboxAuthError
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.bbox.const import SCAN_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_bbox_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with (
        patch("homeassistant.components.bbox.PLATFORMS", [Platform.SENSOR]),
        patch(
            "homeassistant.components.bbox.sensor.utcnow",
            return_value=datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC),
        ),
    ):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.freeze_time("2024-01-01T12:00:00+00:00")
async def test_uptime_sensor(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_bbox_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test uptime sensor calculation."""
    await setup_integration(hass, mock_config_entry)

    uptime_entity = "sensor.bbox_uptime"

    assert (state := hass.states.get(uptime_entity))
    # Router uptime is 630757 seconds, so boot time should be 2023-12-25T04:47:23+00:00
    assert state.state == "2023-12-25T04:47:23+00:00"

    # Update router uptime to 7200 seconds (2 hours)
    mock_bbox_api.get_router_info.return_value.uptime = 7200

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (state := hass.states.get(uptime_entity))
    assert state.state == "2024-01-01T10:01:00+00:00"


async def test_bandwidth_sensors(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_bbox_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test bandwidth sensors."""
    await setup_integration(hass, mock_config_entry)

    down_max_entity = "sensor.bbox_maximum_download_bandwidth"
    up_max_entity = "sensor.bbox_maximum_upload_bandwidth"
    down_current_entity = "sensor.bbox_wan_download_rate"
    up_current_entity = "sensor.bbox_wan_upload_rate"

    # Test maximum bandwidth (8000 Mbps down, 1000 Mbps up)
    assert (state := hass.states.get(down_max_entity))
    assert state.state == "8000.0"
    assert (state := hass.states.get(up_max_entity))
    assert state.state == "1000.0"

    # Test current bandwidth (5432.0 Mbps down, 173.0 Mbps up)
    assert (state := hass.states.get(down_current_entity))
    assert state.state == "5432.0"
    assert (state := hass.states.get(up_current_entity))
    assert state.state == "173.0"

    # Update bandwidth values
    mock_bbox_api.get_wan_ip_stats.return_value.rx.bandwidth = (
        6000000  # 6000 Mbps in kbps
    )
    mock_bbox_api.get_wan_ip_stats.return_value.tx.bandwidth = (
        200000  # 200 Mbps in kbps
    )

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (state := hass.states.get(down_current_entity))
    assert state.state == "6000.0"
    assert (state := hass.states.get(up_current_entity))
    assert state.state == "200.0"


async def test_reboots_sensor(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_bbox_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test number of reboots sensor."""
    await setup_integration(hass, mock_config_entry)

    reboots_entity = "sensor.bbox_number_of_reboots"

    assert (state := hass.states.get(reboots_entity))
    assert state.state == "10"

    # Update number of reboots
    mock_bbox_api.get_router_info.return_value.numberofboots = 6

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (state := hass.states.get(reboots_entity))
    assert state.state == "6"


@pytest.mark.parametrize(
    "side_effect",
    [
        BboxAuthError("Authentication failed"),
        BboxApiError("API error"),
        Exception("Unexpected error"),
    ],
)
async def test_coordinator_update_error(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_bbox_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception,
) -> None:
    """Test coordinator update error handling."""
    await setup_integration(hass, mock_config_entry)

    # Verify sensors are initially available
    uptime_entity = "sensor.bbox_uptime"
    assert (state := hass.states.get(uptime_entity))
    assert state.state != STATE_UNAVAILABLE

    # Simulate error on coordinator update
    mock_bbox_api.get_router_info.side_effect = side_effect

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Sensors should be unavailable after error
    assert (state := hass.states.get(uptime_entity))
    assert state.state == STATE_UNAVAILABLE


async def test_sensor_availability(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_bbox_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor availability recovery."""
    await setup_integration(hass, mock_config_entry)

    uptime_entity = "sensor.bbox_uptime"

    # Initially available
    assert (state := hass.states.get(uptime_entity))
    assert state.state != STATE_UNAVAILABLE

    # Make sensor unavailable
    mock_bbox_api.get_router_info.side_effect = BboxApiError("Temporary error")

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (state := hass.states.get(uptime_entity))
    assert state.state == STATE_UNAVAILABLE

    # Recover from error
    mock_bbox_api.get_router_info.side_effect = None

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Should be available again
    assert (state := hass.states.get(uptime_entity))
    assert state.state != STATE_UNAVAILABLE
