"""Tests for Hypontech sensors."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.hypontech.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def test_sensors(
    hass: HomeAssistant,
    mock_hyponcloud: AsyncMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Hypontech sensors."""
    with patch("homeassistant.components.hypontech._PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_monitor_fetched_only_for_enabled_plants(
    hass: HomeAssistant,
    mock_hyponcloud: AsyncMock,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Monitor data is only fetched for plants with an enabled monitor entity."""
    mock_config_entry.add_to_hass(hass)
    # Disable every monitor-backed sensor of the non-storage "Rooftop" plant.
    for key in ("pv_power", "load_power", "grid_power"):
        entity_registry.async_get_or_create(
            "sensor",
            DOMAIN,
            f"3123456789123456789_{key}",
            config_entry=mock_config_entry,
            disabled_by=er.RegistryEntryDisabler.USER,
        )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # The first refresh fetches every plant; subsequent refreshes are gated by
    # which plants have an enabled monitor entity.
    mock_hyponcloud.get_monitor.reset_mock()
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    fetched_plant_ids = {
        call.args[0] for call in mock_hyponcloud.get_monitor.call_args_list
    }
    assert fetched_plant_ids == {"1123456789123456789"}
