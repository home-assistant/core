"""Tests for Essent sensors."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.essent.const import UPDATE_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

# Freeze time to match fixture download moment (2025-11-24 at 14:11 CET)
pytestmark = pytest.mark.freeze_time("2025-11-24T14:11:00+01:00")


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_essent_client")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    setup_sensor_entry: MockConfigEntry,
) -> None:
    """Test all sensor entities via snapshot."""
    await snapshot_platform(
        hass, entity_registry, snapshot, setup_sensor_entry.entry_id
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_essent_client")
async def test_sensor_updates_on_hour_tick(
    hass: HomeAssistant,
    mock_essent_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    setup_sensor_entry: MockConfigEntry,
) -> None:
    """Test sensors update when hourly listener fires."""
    # Initial fetch on setup
    assert mock_essent_client.async_get_prices.call_count == 1

    # Jump exactly to the next hour boundary from the current frozen time
    now = dt_util.utcnow()
    minutes_until_hour = 60 - now.minute
    freezer.tick(timedelta(minutes=minutes_until_hour))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Hourly tick should not trigger an extra API call
    assert mock_essent_client.async_get_prices.call_count == 1

    # Snapshot platform state after the tick
    await snapshot_platform(
        hass, entity_registry, snapshot, setup_sensor_entry.entry_id
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_coordinator_refresh_updates_data(
    hass: HomeAssistant,
    mock_essent_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
    setup_sensor_entry: MockConfigEntry,
) -> None:
    """Test coordinator refresh fetches new data."""
    # Verify async_get_prices called once on setup
    assert mock_essent_client.async_get_prices.call_count == 1

    # Advance time by UPDATE_INTERVAL (1 hour)
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Verify async_get_prices called twice (coordinator refreshed)
    assert mock_essent_client.async_get_prices.call_count == 2
