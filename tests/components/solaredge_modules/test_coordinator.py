"""Tests for the SolarEdge Modules coordinator."""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from solaredge_web import EnergyData

from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.statistics import statistics_during_period
from homeassistant.components.solaredge_modules.coordinator import (
    SolarEdgeModulesCoordinator,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.recorder.common import async_wait_recording_done


async def _trigger_and_wait_for_refresh(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    coordinator: SolarEdgeModulesCoordinator,
) -> None:
    """Trigger a coordinator refresh and wait for it to complete."""
    # The coordinator refresh runs in the background.
    # To reliably assert the result, we need to wait for the refresh to complete.
    # We patch the coordinator's update method to signal completion via an asyncio.Event.
    refresh_done = asyncio.Event()
    original_update = coordinator._async_update_data

    async def wrapped_update_data() -> None:
        """Wrap original update and set event."""
        await original_update()
        refresh_done.set()

    with patch.object(
        coordinator,
        "_async_update_data",
        side_effect=wrapped_update_data,
        autospec=True,
    ):
        freezer.tick(timedelta(hours=12))
        async_fire_time_changed(hass)
        await asyncio.wait_for(refresh_done.wait(), timeout=5)


async def test_coordinator_first_run(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_solar_edge_web: AsyncMock,
) -> None:
    """Test the coordinator on its first run with no existing statistics."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await async_wait_recording_done(hass)
    stats = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        dt_util.as_utc(datetime(1970, 1, 1, 0, 0)),
        None,
        {
            "solaredge_modules:123456_1001",
            "solaredge_modules:123456_1002",
        },
        "hour",
        None,
        {"state", "sum"},
    )
    assert stats == {
        "solaredge_modules:123456_1001": [
            {
                "start": 1735783200.0,
                "end": 1735786800.0,
                "state": 11.5,
                "sum": 11.5,
            },
            {
                "start": 1735786800.0,
                "end": 1735790400.0,
                "state": 15.5,
                "sum": 27.0,
            },
        ],
        "solaredge_modules:123456_1002": [
            {
                "start": 1735783200.0,
                "end": 1735786800.0,
                "state": 21.5,
                "sum": 21.5,
            },
            {
                "start": 1735786800.0,
                "end": 1735790400.0,
                "state": 25.5,
                "sum": 47.0,
            },
        ],
    }


async def test_coordinator_subsequent_run(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_solar_edge_web: AsyncMock,
) -> None:
    """Test the coordinator correctly updates statistics on subsequent runs."""
    mock_solar_edge_web.async_get_equipment.return_value = {
        1001: {"displayName": "1.1"},
    }

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    mock_solar_edge_web.async_get_energy_data.return_value = [
        # Updated values, different from the first run
        EnergyData(
            start_time=dt_util.as_utc(datetime(2025, 1, 1, 11, 0)),
            values={1001: 24.0},
        ),
        EnergyData(
            start_time=dt_util.as_utc(datetime(2025, 1, 1, 11, 15)),
            values={1001: 25.0},
        ),
        EnergyData(
            start_time=dt_util.as_utc(datetime(2025, 1, 1, 11, 30)),
            values={1001: 26.0},
        ),
        EnergyData(
            start_time=dt_util.as_utc(datetime(2025, 1, 1, 11, 45)),
            values={1001: 27.0},
        ),
        # New values for the next hour
        EnergyData(
            start_time=dt_util.as_utc(datetime(2025, 1, 1, 12, 0)),
            values={1001: 28.0},
        ),
        EnergyData(
            start_time=dt_util.as_utc(datetime(2025, 1, 1, 12, 15)),
            values={1001: 29.0},
        ),
        EnergyData(
            start_time=dt_util.as_utc(datetime(2025, 1, 1, 12, 30)),
            values={1001: 30.0},
        ),
        EnergyData(
            start_time=dt_util.as_utc(datetime(2025, 1, 1, 12, 45)),
            values={1001: 31.0},
        ),
    ]

    coordinator: SolarEdgeModulesCoordinator = mock_config_entry.runtime_data
    await _trigger_and_wait_for_refresh(hass, freezer, coordinator)

    await async_wait_recording_done(hass)
    stats = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        dt_util.as_utc(datetime(1970, 1, 1, 0, 0)),
        None,
        {
            "solaredge_modules:123456_1001",
            "solaredge_modules:123456_1002",
        },
        "hour",
        None,
        {"state", "sum"},
    )
    assert stats == {
        "solaredge_modules:123456_1001": [
            {
                "start": 1735783200.0,
                "end": 1735786800.0,
                "state": 11.5,
                "sum": 11.5,
            },
            {
                "start": 1735786800.0,
                "end": 1735790400.0,
                "state": 25.5,
                "sum": 37.0,
            },
            {
                "start": 1735790400.0,
                "end": 1735794000.0,
                "state": 29.5,
                "sum": 66.5,
            },
        ]
    }


async def test_coordinator_subsequent_run_with_gap(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_solar_edge_web: AsyncMock,
) -> None:
    """Test the coordinator correctly updates statistics on subsequent runs with a gap in data."""
    mock_solar_edge_web.async_get_equipment.return_value = {
        1001: {"displayName": "1.1"},
    }

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    mock_solar_edge_web.async_get_energy_data.return_value = [
        # New values a month later, simulating a gap in data
        EnergyData(
            start_time=dt_util.as_utc(datetime(2025, 2, 1, 11, 0)),
            values={1001: 24.0},
        ),
        EnergyData(
            start_time=dt_util.as_utc(datetime(2025, 2, 1, 11, 15)),
            values={1001: 25.0},
        ),
        EnergyData(
            start_time=dt_util.as_utc(datetime(2025, 2, 1, 11, 30)),
            values={1001: 26.0},
        ),
        EnergyData(
            start_time=dt_util.as_utc(datetime(2025, 2, 1, 11, 45)),
            values={1001: 27.0},
        ),
    ]

    coordinator: SolarEdgeModulesCoordinator = mock_config_entry.runtime_data
    await _trigger_and_wait_for_refresh(hass, freezer, coordinator)

    await async_wait_recording_done(hass)
    stats = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        dt_util.as_utc(datetime(1970, 1, 1, 0, 0)),
        None,
        {
            "solaredge_modules:123456_1001",
            "solaredge_modules:123456_1002",
        },
        "hour",
        None,
        {"state", "sum"},
    )
    assert stats == {
        "solaredge_modules:123456_1001": [
            {
                "start": 1735783200.0,
                "end": 1735786800.0,
                "state": 11.5,
                "sum": 11.5,
            },
            {
                "start": 1735786800.0,
                "end": 1735790400.0,
                "state": 15.5,
                "sum": 27.0,
            },
            {
                "start": 1738465200.0,
                "end": 1738468800.0,
                "state": 25.5,
                "sum": 52.5,
            },
        ]
    }


async def test_coordinator_no_energy_data(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_solar_edge_web: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the coordinator handles an empty energy data response from the API."""
    mock_solar_edge_web.async_get_energy_data.return_value = []

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert "No data received from SolarEdge API" in caplog.text

    await async_wait_recording_done(hass)
    stats = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        dt_util.as_utc(datetime(1970, 1, 1, 0, 0)),
        None,
        {
            "solaredge_modules:123456_1001",
            "solaredge_modules:123456_1002",
        },
        "hour",
        None,
        {"state", "sum"},
    )
    assert not stats
