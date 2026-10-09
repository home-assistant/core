"""Tests for the AdGuard Home sensor entities."""

from datetime import timedelta
from unittest.mock import AsyncMock

from adguardhome import (
    AdGuardHomeAuthenticationError,
    AdGuardHomeConnectionError,
    AdGuardHomeResponseError,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.adguard.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

STATISTICS_INTERVAL = timedelta(minutes=5)


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.SENSOR]


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the adguard sensor platform."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_sensors_share_one_request(
    hass: HomeAssistant,
    mock_adguard: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test all sensors are updated from a single request for the statistics."""
    mock_adguard.stats.get.reset_mock()
    mock_adguard.filtering.blocklists.list.reset_mock()

    freezer.tick(STATISTICS_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_adguard.stats.get.call_count == 1
    assert mock_adguard.filtering.blocklists.list.call_count == 1


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    "error",
    [
        AdGuardHomeConnectionError("Connection error"),
        AdGuardHomeResponseError("Server error", status=500, body=""),
    ],
)
async def test_sensors_unavailable(
    hass: HomeAssistant,
    mock_adguard: AsyncMock,
    freezer: FrozenDateTimeFactory,
    error: Exception,
) -> None:
    """Test the sensors are unavailable while AdGuard Home fails, and recover."""
    mock_adguard.stats.get.side_effect = error

    freezer.tick(STATISTICS_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("sensor.adguard_home_dns_queries")
    assert state
    assert state.state == STATE_UNAVAILABLE

    mock_adguard.stats.get.side_effect = None

    freezer.tick(STATISTICS_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("sensor.adguard_home_dns_queries")
    assert state
    assert state.state == "666"


async def test_sensors_authentication_failed(
    hass: HomeAssistant,
    mock_adguard: AsyncMock,
    init_integration: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test credentials rejected while updating ask for new ones."""
    mock_adguard.stats.get.side_effect = AdGuardHomeAuthenticationError("Nope")

    freezer.tick(STATISTICS_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("sensor.adguard_home_dns_queries")
    assert state
    assert state.state == STATE_UNAVAILABLE

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == init_integration.entry_id
