"""Tests for the ista EcoTrend Statistics import."""

import datetime
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.recorder.statistics import statistics_during_period
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import extend_statistics

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.recorder.common import async_wait_recording_done


@pytest.mark.usefixtures("recorder_mock", "entity_registry_enabled_by_default")
async def test_statistics_import(
    hass: HomeAssistant,
    ista_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_ista: MagicMock,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test setup of ista EcoTrend sensor platform."""

    ista_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(ista_config_entry.entry_id)
    await hass.async_block_till_done()

    assert ista_config_entry.state is ConfigEntryState.LOADED
    entities = er.async_entries_for_config_entry(
        entity_registry, ista_config_entry.entry_id
    )
    await async_wait_recording_done(hass)

    # Test that consumption statistics for 2 months have been added
    for entity in entities:
        statistic_id = f"ista_ecotrend:{entity.entity_id.removeprefix('sensor.')}"
        stats = await hass.async_add_executor_job(
            statistics_during_period,
            hass,
            datetime.datetime.fromtimestamp(0, tz=datetime.UTC),
            None,
            {statistic_id},
            "month",
            None,
            {"state", "sum"},
        )
        assert stats[statistic_id] == snapshot(name=f"{statistic_id}_2months")
        assert len(stats[statistic_id]) == 2

    # Add another monthly consumption and forward
    # 1 day and test if the new values have been
    # appended to the statistics
    mock_ista.get_consumption_data = extend_statistics

    freezer.tick(datetime.timedelta(days=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)
    freezer.tick(datetime.timedelta(days=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    for entity in entities:
        statistic_id = f"ista_ecotrend:{entity.entity_id.removeprefix('sensor.')}"
        stats = await hass.async_add_executor_job(
            statistics_during_period,
            hass,
            datetime.datetime.fromtimestamp(0, tz=datetime.UTC),
            None,
            {statistic_id},
            "month",
            None,
            {"state", "sum"},
        )
        assert stats[statistic_id] == snapshot(name=f"{statistic_id}_3months")

        assert len(stats[statistic_id]) == 3
