"""Tests for the SolarEdge Modules coordinator."""

from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from solaredge_web import EnergyData
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.statistics import statistics_during_period
from homeassistant.components.solaredge_modules.coordinator import (
    SolarEdgeModulesCoordinator,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry
from tests.components.recorder.common import async_wait_recording_done


async def test_coordinator_first_run(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_solar_edge_web: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the coordinator on its first run with no existing statistics."""
    coordinator = SolarEdgeModulesCoordinator(hass, mock_config_entry)
    await coordinator._async_update_data()

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
    assert stats == snapshot


async def test_coordinator_subsequent_run(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_solar_edge_web: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the coordinator correctly updates statistics on subsequent runs."""
    mock_solar_edge_web.async_get_equipment.return_value = {
        1001: {"displayName": "1.1"},
    }

    coordinator = SolarEdgeModulesCoordinator(hass, mock_config_entry)

    # Run the coordinator for the first time to create initial statistics
    await coordinator._async_update_data()
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

    # Run the coordinator again to process the new data
    await coordinator._async_update_data()

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
    assert stats == snapshot


async def test_coordinator_subsequent_run_with_gap(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_solar_edge_web: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the coordinator correctly updates statistics on subsequent runs with a gap in data."""
    mock_solar_edge_web.async_get_equipment.return_value = {
        1001: {"displayName": "1.1"},
    }

    coordinator = SolarEdgeModulesCoordinator(hass, mock_config_entry)

    # Run the coordinator for the first time to create initial statistics
    await coordinator._async_update_data()
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

    # Run the coordinator again to process the new data
    await coordinator._async_update_data()

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
    assert stats == snapshot


async def test_coordinator_no_energy_data(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_solar_edge_web: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the coordinator handles an empty energy data response from the API."""
    mock_solar_edge_web.async_get_energy_data.return_value = []

    coordinator = SolarEdgeModulesCoordinator(hass, mock_config_entry)
    await coordinator._async_update_data()

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
