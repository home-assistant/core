"""Tests for the AdGuard Home sensor entities."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.adguard.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


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
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the adguard sensor platform."""
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_disabled_sensors_do_not_update(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_adguard: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that disabled sensors do not query the API during setup or polling."""
    entity_registry.async_get_or_create(
        Platform.SENSOR,
        DOMAIN,
        "adguard_127.0.0.1_3000_sensor_dns_queries",
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # No sensors update during setup (update_before_add=False)
    mock_adguard.stats.avg_processing_time.assert_not_called()
    mock_adguard.stats.dns_queries.assert_not_called()
    mock_adguard.filtering.rules_count.assert_not_called()

    # After polling interval, only enabled sensors update
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_adguard.stats.avg_processing_time.assert_called_once()
    mock_adguard.stats.dns_queries.assert_not_called()
    mock_adguard.filtering.rules_count.assert_not_called()
