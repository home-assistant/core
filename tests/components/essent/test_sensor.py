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

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

# Freeze time to match fixture download moment (2025-11-24 at 14:11 CET)
pytestmark = pytest.mark.freeze_time("2025-11-24T14:11:00+01:00")


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_essent_client")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test all sensor entities via snapshot."""
    await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_essent_client")
async def test_sensor_updates_on_hour_tick(
    hass: HomeAssistant,
    mock_essent_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensors update when hourly listener fires."""
    await setup_integration(hass, mock_config_entry)
    # Initial fetch on setup
    assert mock_essent_client.async_get_prices.call_count == 1

    assert (
        hass.states.get("sensor.essent_current_electricity_market_price").state
        == "0.17595"
    )

    # Jump exactly to the next hour boundary from the current frozen time
    now = dt_util.utcnow()
    minutes_until_hour = 60 - now.minute
    freezer.tick(timedelta(minutes=minutes_until_hour))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Hourly tick should not trigger an extra API call
    assert mock_essent_client.async_get_prices.call_count == 1

    assert (
        hass.states.get("sensor.essent_current_electricity_market_price").state
        == "0.21181"
    )

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_essent_client.async_get_prices.call_count == 2

    assert (
        hass.states.get("sensor.essent_current_electricity_market_price").state
        == "0.10417"
    )
