"""Tests for the Tesla Fleet energy history coordinator."""

from datetime import timedelta
from typing import Literal
from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion
from tesla_fleet_api.exceptions import RateLimited, TeslaFleetError

from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.statistics import statistics_during_period
from homeassistant.components.tesla_fleet.coordinator import (
    TeslaFleetEnergySiteHistoryCoordinator,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util

from .conftest import UID

from tests.common import MockConfigEntry
from tests.components.recorder.common import async_wait_recording_done

# Typed set for statistics_during_period types parameter
STATISTIC_TYPES: set[
    Literal["change", "last_reset", "max", "mean", "min", "state", "sum"]
] = {"state", "sum"}


@pytest.fixture(autouse=True)
def mock_recorder_functions() -> None:
    """Override the autouse mock_recorder_functions from conftest.py.

    This fixture overrides the conftest.py version to NOT mock recorder functions,
    allowing tests in this file to use the real recorder.
    """


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a simple mock config entry for coordinator tests."""
    return MockConfigEntry(
        domain="tesla_fleet",
        title=UID,
        unique_id=UID,
        data={},
    )


@pytest.fixture
def mock_energy_site() -> AsyncMock:
    """Create a mock EnergySite API."""
    mock_api = AsyncMock()
    mock_api.energy_site_id = "123456"
    return mock_api


async def test_coordinator_first_run(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_energy_site: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the coordinator on its first run with no existing statistics."""
    # Mock energy history response
    mock_energy_site.energy_history.return_value = {
        "response": {
            "period": "day",
            "time_series": [
                {
                    "timestamp": "2023-06-01T08:00:00-07:00",
                    "solar_energy_exported": 1000,
                    "grid_energy_imported": 500,
                    "battery_energy_exported": 200,
                },
                {
                    "timestamp": "2023-06-01T09:00:00-07:00",
                    "solar_energy_exported": 1500,
                    "grid_energy_imported": 300,
                    "battery_energy_exported": 100,
                },
            ],
        }
    }

    mock_config_entry.add_to_hass(hass)

    # Create and run coordinator
    with patch(
        "homeassistant.components.tesla_fleet.coordinator.get_instance"
    ) as mock_get_instance:
        mock_get_instance.return_value = recorder_mock
        coordinator = TeslaFleetEnergySiteHistoryCoordinator(
            hass, mock_config_entry, mock_energy_site
        )
        await coordinator._async_update_data()

    await async_wait_recording_done(hass)

    # Check stats were created
    stats = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        dt_util.utc_from_timestamp(0),
        None,
        {
            "tesla_fleet:123456_solar_energy_exported",
            "tesla_fleet:123456_grid_energy_imported",
            "tesla_fleet:123456_battery_energy_exported",
        },
        "hour",
        None,
        STATISTIC_TYPES,
    )
    assert stats == snapshot


async def test_coordinator_subsequent_run(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_energy_site: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the coordinator correctly updates statistics on subsequent runs."""
    mock_config_entry.add_to_hass(hass)

    # First run
    mock_energy_site.energy_history.return_value = {
        "response": {
            "period": "day",
            "time_series": [
                {
                    "timestamp": "2023-06-01T08:00:00-07:00",
                    "solar_energy_exported": 1000,
                    "grid_energy_imported": 500,
                },
            ],
        }
    }

    with patch(
        "homeassistant.components.tesla_fleet.coordinator.get_instance"
    ) as mock_get_instance:
        mock_get_instance.return_value = recorder_mock
        coordinator = TeslaFleetEnergySiteHistoryCoordinator(
            hass, mock_config_entry, mock_energy_site
        )
        await coordinator._async_update_data()
        await async_wait_recording_done(hass)

        # Second run with additional data
        mock_energy_site.energy_history.return_value = {
            "response": {
                "period": "day",
                "time_series": [
                    {
                        "timestamp": "2023-06-01T08:00:00-07:00",
                        "solar_energy_exported": 1000,
                        "grid_energy_imported": 500,
                    },
                    {
                        "timestamp": "2023-06-01T09:00:00-07:00",
                        "solar_energy_exported": 2000,
                        "grid_energy_imported": 300,
                    },
                ],
            }
        }

        await coordinator._async_update_data()
        await async_wait_recording_done(hass)

    # Check all stats - should have both time periods
    stats = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        dt_util.utc_from_timestamp(0),
        None,
        {
            "tesla_fleet:123456_solar_energy_exported",
            "tesla_fleet:123456_grid_energy_imported",
        },
        "hour",
        None,
        STATISTIC_TYPES,
    )
    assert stats == snapshot


async def test_coordinator_skips_existing_timestamps(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_energy_site: AsyncMock,
) -> None:
    """Test the coordinator skips timestamps that already exist."""
    mock_config_entry.add_to_hass(hass)

    # First run
    mock_energy_site.energy_history.return_value = {
        "response": {
            "period": "day",
            "time_series": [
                {
                    "timestamp": "2023-06-01T08:00:00-07:00",
                    "solar_energy_exported": 1000,
                },
            ],
        }
    }

    with patch(
        "homeassistant.components.tesla_fleet.coordinator.get_instance"
    ) as mock_get_instance:
        mock_get_instance.return_value = recorder_mock
        coordinator = TeslaFleetEnergySiteHistoryCoordinator(
            hass, mock_config_entry, mock_energy_site
        )
        await coordinator._async_update_data()
        await async_wait_recording_done(hass)

        # Second run with same data - should not add duplicates
        await coordinator._async_update_data()
        await async_wait_recording_done(hass)

    # Verify only one stat entry exists
    stats = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        dt_util.utc_from_timestamp(0),
        None,
        {"tesla_fleet:123456_solar_energy_exported"},
        "hour",
        None,
        STATISTIC_TYPES,
    )

    assert len(stats["tesla_fleet:123456_solar_energy_exported"]) == 1


async def test_coordinator_handles_empty_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_energy_site: AsyncMock,
) -> None:
    """Test the coordinator handles empty time_series data."""
    mock_config_entry.add_to_hass(hass)

    mock_energy_site.energy_history.return_value = {
        "response": {
            "period": "day",
            "time_series": [],
        }
    }

    coordinator = TeslaFleetEnergySiteHistoryCoordinator(
        hass, mock_config_entry, mock_energy_site
    )

    # Should not raise an error
    await coordinator._async_update_data()
    assert coordinator.updated_once is True


async def test_coordinator_handles_invalid_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_energy_site: AsyncMock,
) -> None:
    """Test the coordinator raises UpdateFailed for invalid data."""
    mock_config_entry.add_to_hass(hass)

    mock_energy_site.energy_history.return_value = {
        "not_response": {
            "period": "day",
        }
    }

    coordinator = TeslaFleetEnergySiteHistoryCoordinator(
        hass, mock_config_entry, mock_energy_site
    )

    with pytest.raises(UpdateFailed, match="Received invalid data"):
        await coordinator._async_update_data()


async def test_coordinator_normalizes_timestamps_to_hour(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_energy_site: AsyncMock,
) -> None:
    """Test the coordinator normalizes timestamps to the top of the hour."""
    mock_config_entry.add_to_hass(hass)

    raw_timestamp = "2023-06-01T08:12:34-07:00"
    expected_start = dt_util.parse_datetime(raw_timestamp)
    assert expected_start is not None
    expected_start = expected_start.replace(minute=0, second=0, microsecond=0)

    mock_energy_site.energy_history.return_value = {
        "response": {
            "period": "day",
            "time_series": [
                {
                    "timestamp": raw_timestamp,
                    "solar_energy_exported": 1234,
                },
            ],
        }
    }

    with patch(
        "homeassistant.components.tesla_fleet.coordinator.get_instance"
    ) as mock_get_instance:
        mock_get_instance.return_value = recorder_mock
        coordinator = TeslaFleetEnergySiteHistoryCoordinator(
            hass, mock_config_entry, mock_energy_site
        )
        await coordinator._async_update_data()

    await async_wait_recording_done(hass)

    stats = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        dt_util.utc_from_timestamp(0),
        None,
        {"tesla_fleet:123456_solar_energy_exported"},
        "hour",
        None,
        STATISTIC_TYPES,
    )

    assert len(stats["tesla_fleet:123456_solar_energy_exported"]) == 1
    stat = stats["tesla_fleet:123456_solar_energy_exported"][0]
    assert stat["start"] == dt_util.as_utc(expected_start).timestamp()
    assert stat["state"] == 1234.0
    assert stat["sum"] == 1234.0


async def test_coordinator_handles_rate_limiting(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_energy_site: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the coordinator handles rate limiting."""
    mock_config_entry.add_to_hass(hass)

    mock_energy_site.energy_history.side_effect = RateLimited({"after": "120"})

    coordinator = TeslaFleetEnergySiteHistoryCoordinator(
        hass, mock_config_entry, mock_energy_site
    )
    await coordinator._async_update_data()

    assert "rate limited" in caplog.text.lower()
    assert coordinator.update_interval == timedelta(seconds=120)


async def test_coordinator_handles_api_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_energy_site: AsyncMock,
) -> None:
    """Test the coordinator handles API errors."""
    mock_config_entry.add_to_hass(hass)

    mock_energy_site.energy_history.side_effect = TeslaFleetError

    coordinator = TeslaFleetEnergySiteHistoryCoordinator(
        hass, mock_config_entry, mock_energy_site
    )

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_coordinator_handles_missing_timestamp(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_energy_site: AsyncMock,
) -> None:
    """Test the coordinator skips entries with missing timestamps."""
    mock_config_entry.add_to_hass(hass)

    mock_energy_site.energy_history.return_value = {
        "response": {
            "period": "day",
            "time_series": [
                {
                    "solar_energy_exported": 1000,
                },
                {
                    "timestamp": "2023-06-01T08:00:00-07:00",
                    "solar_energy_exported": 2000,
                },
            ],
        }
    }

    with patch(
        "homeassistant.components.tesla_fleet.coordinator.get_instance"
    ) as mock_get_instance:
        mock_get_instance.return_value = recorder_mock
        coordinator = TeslaFleetEnergySiteHistoryCoordinator(
            hass, mock_config_entry, mock_energy_site
        )
        await coordinator._async_update_data()
        await async_wait_recording_done(hass)

    # Should only have one stat (the entry with timestamp)
    stats = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        dt_util.utc_from_timestamp(0),
        None,
        {"tesla_fleet:123456_solar_energy_exported"},
        "hour",
        None,
        STATISTIC_TYPES,
    )

    assert len(stats["tesla_fleet:123456_solar_energy_exported"]) == 1
    assert stats["tesla_fleet:123456_solar_energy_exported"][0].get("sum") == 2000
