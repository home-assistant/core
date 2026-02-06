"""Tests for Ghost sensors."""

from datetime import timedelta
from unittest.mock import AsyncMock

from aioghost.exceptions import GhostError
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import NEWSLETTERS_DATA

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_ghost_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Snapshot all Ghost sensor entities."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_newsletter_sensor_added_on_update(
    hass: HomeAssistant,
    mock_ghost_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test newsletter sensors are added after updates."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.test_ghost_monthly_subscribers") is None

    mock_ghost_api.get_newsletters.return_value = [
        *NEWSLETTERS_DATA,
        {
            "id": "nl3",
            "name": "Monthly",
            "status": "active",
            "count": {"members": 300},
        },
    ]

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("sensor.test_ghost_monthly_subscribers")
    assert state is not None
    assert state.state == "300"


async def test_revenue_sensors_not_created_without_stripe(
    hass: HomeAssistant, mock_ghost_api: AsyncMock, mock_config_entry
) -> None:
    """Test MRR/ARR sensors are not created when Stripe is not linked."""
    # Return empty MRR/ARR data (no Stripe linked)
    mock_ghost_api.get_mrr.return_value = {}
    mock_ghost_api.get_arr.return_value = {}

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.test_ghost_mrr") is None
    assert hass.states.get("sensor.test_ghost_arr") is None


async def test_newsletter_sensor_not_found(
    hass: HomeAssistant,
    mock_ghost_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test newsletter sensor when newsletter is removed."""
    await setup_integration(hass, mock_config_entry)

    # Verify newsletter sensor exists
    state = hass.states.get("sensor.test_ghost_weekly_subscribers")
    assert state is not None
    assert state.state == "800"

    # Now return empty newsletters list
    mock_ghost_api.get_newsletters.return_value = []

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Sensor should now be unavailable (newsletter not found)
    state = hass.states.get("sensor.test_ghost_weekly_subscribers")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_entities_unavailable_on_update_failure(
    hass: HomeAssistant,
    mock_ghost_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test entities become unavailable on update failure."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.test_ghost_total_members")
    assert state is not None
    assert state.state == "1000"

    mock_ghost_api.get_site.side_effect = GhostError("Update failed")

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("sensor.test_ghost_total_members")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
