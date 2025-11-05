"""Tests for the SolarEdge coordinator services."""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from solaredge_web import EnergyData

from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.statistics import statistics_during_period
from homeassistant.components.solaredge.const import (
    CONF_SITE_ID,
    DATA_MODULES_COORDINATOR,
    DEFAULT_NAME,
    DOMAIN,
    OVERVIEW_UPDATE_DELAY,
)
from homeassistant.components.solaredge.coordinator import SolarEdgeModulesCoordinator
from homeassistant.const import (
    CONF_API_KEY,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .conftest import API_KEY, PASSWORD, SITE_ID, USERNAME

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.recorder.common import async_wait_recording_done


@pytest.fixture(autouse=True)
def enable_all_entities(entity_registry_enabled_by_default: None) -> None:
    """Make sure all entities are enabled."""


@patch("homeassistant.components.solaredge.SolarEdge")
async def test_solaredgeoverviewdataservice_energy_values_validity(
    mock_solaredge,
    recorder_mock: Recorder,
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test overview energy data validity."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        title=DEFAULT_NAME,
        data={CONF_NAME: DEFAULT_NAME, CONF_SITE_ID: SITE_ID, CONF_API_KEY: API_KEY},
    )
    mock_solaredge().get_details = AsyncMock(
        return_value={"details": {"status": "active"}}
    )
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Valid energy values update
    mock_overview_data = {
        "overview": {
            "lifeTimeData": {"energy": 100000},
            "lastYearData": {"energy": 50000},
            "lastMonthData": {"energy": 10000},
            "lastDayData": {"energy": 0.0},
            "currentPower": {"power": 0.0},
        }
    }
    mock_solaredge().get_overview = AsyncMock(return_value=mock_overview_data)
    freezer.tick(OVERVIEW_UPDATE_DELAY)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    state = hass.states.get("sensor.solaredge_lifetime_energy")
    assert state
    assert state.state == str(mock_overview_data["overview"]["lifeTimeData"]["energy"])

    # Invalid energy values, lifeTimeData energy is lower than last year, month or day.
    mock_overview_data["overview"]["lifeTimeData"]["energy"] = 0
    mock_solaredge().get_overview = AsyncMock(return_value=mock_overview_data)
    freezer.tick(OVERVIEW_UPDATE_DELAY)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("sensor.solaredge_lifetime_energy")
    assert state
    assert state.state == STATE_UNKNOWN

    # New valid energy values update
    mock_overview_data["overview"]["lifeTimeData"]["energy"] = 100001
    mock_solaredge().get_overview = AsyncMock(return_value=mock_overview_data)
    freezer.tick(OVERVIEW_UPDATE_DELAY)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("sensor.solaredge_lifetime_energy")
    assert state
    assert state.state == str(mock_overview_data["overview"]["lifeTimeData"]["energy"])

    # Invalid energy values, lastYearData energy is lower than last month or day.
    mock_overview_data["overview"]["lastYearData"]["energy"] = 0
    mock_solaredge().get_overview = AsyncMock(return_value=mock_overview_data)
    freezer.tick(OVERVIEW_UPDATE_DELAY)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("sensor.solaredge_energy_this_year")
    assert state
    assert state.state == STATE_UNKNOWN
    # Check that the valid lastMonthData is still available
    state = hass.states.get("sensor.solaredge_energy_this_month")
    assert state
    assert state.state == str(mock_overview_data["overview"]["lastMonthData"]["energy"])

    # All zero energy values should also be valid.
    mock_overview_data["overview"]["lifeTimeData"]["energy"] = 0.0
    mock_overview_data["overview"]["lastYearData"]["energy"] = 0.0
    mock_overview_data["overview"]["lastMonthData"]["energy"] = 0.0
    mock_overview_data["overview"]["lastDayData"]["energy"] = 0.0
    mock_solaredge().get_overview = AsyncMock(return_value=mock_overview_data)
    freezer.tick(OVERVIEW_UPDATE_DELAY)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("sensor.solaredge_lifetime_energy")
    assert state
    assert state.state == str(mock_overview_data["overview"]["lifeTimeData"]["energy"])


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


@pytest.fixture
def mock_solar_edge_web() -> AsyncMock:
    """Mock SolarEdgeWeb."""
    with patch(
        "homeassistant.components.solaredge.coordinator.SolarEdgeWeb", autospec=True
    ) as mock_api:
        api = mock_api.return_value
        api.async_get_equipment.return_value = {
            1001: {"displayName": "1.1"},
            1002: {"displayName": "1.2"},
        }
        api.async_get_energy_data.return_value = [
            EnergyData(
                start_time=dt_util.as_utc(datetime(2025, 1, 1, 10, 0)),
                values={1001: 10.0, 1002: 20.0},
            ),
            EnergyData(
                start_time=dt_util.as_utc(datetime(2025, 1, 1, 10, 15)),
                values={1001: 11.0, 1002: 21.0},
            ),
            EnergyData(
                start_time=dt_util.as_utc(datetime(2025, 1, 1, 10, 30)),
                values={1001: 12.0, 1002: 22.0},
            ),
            EnergyData(
                start_time=dt_util.as_utc(datetime(2025, 1, 1, 10, 45)),
                values={1001: 13.0, 1002: 23.0},
            ),
            EnergyData(
                start_time=dt_util.as_utc(datetime(2025, 1, 1, 11, 0)),
                values={1001: 14.0, 1002: 24.0},
            ),
            EnergyData(
                start_time=dt_util.as_utc(datetime(2025, 1, 1, 11, 15)),
                values={1001: 15.0, 1002: 25.0},
            ),
            EnergyData(
                start_time=dt_util.as_utc(datetime(2025, 1, 1, 11, 30)),
                values={1001: 16.0, 1002: 26.0},
            ),
            EnergyData(
                start_time=dt_util.as_utc(datetime(2025, 1, 1, 11, 45)),
                values={1001: 17.0, 1002: 27.0},
            ),
        ]
        yield api


async def test_modules_coordinator_first_run(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_solar_edge_web: AsyncMock,
) -> None:
    """Test the modules coordinator on its first run with no existing statistics."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_SITE_ID: SITE_ID, CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await async_wait_recording_done(hass)
    stats = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        dt_util.as_utc(datetime(1970, 1, 1, 0, 0)),
        None,
        {f"{DOMAIN}:{SITE_ID}_1001", f"{DOMAIN}:{SITE_ID}_1002"},
        "hour",
        None,
        {"state", "sum"},
    )
    assert stats == {
        f"{DOMAIN}:{SITE_ID}_1001": [
            {"start": 1735783200.0, "end": 1735786800.0, "state": 11.5, "sum": 11.5},
            {"start": 1735786800.0, "end": 1735790400.0, "state": 15.5, "sum": 27.0},
        ],
        f"{DOMAIN}:{SITE_ID}_1002": [
            {"start": 1735783200.0, "end": 1735786800.0, "state": 21.5, "sum": 21.5},
            {"start": 1735786800.0, "end": 1735790400.0, "state": 25.5, "sum": 47.0},
        ],
    }


async def test_modules_coordinator_subsequent_run(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_solar_edge_web: AsyncMock,
) -> None:
    """Test the coordinator correctly updates statistics on subsequent runs."""
    mock_solar_edge_web.async_get_equipment.return_value = {
        1001: {"displayName": "1.1"},
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_SITE_ID: SITE_ID, CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
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

    coordinator: SolarEdgeModulesCoordinator = entry.runtime_data[
        DATA_MODULES_COORDINATOR
    ]
    await _trigger_and_wait_for_refresh(hass, freezer, coordinator)
    await async_wait_recording_done(hass)

    stats = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        dt_util.as_utc(datetime(1970, 1, 1, 0, 0)),
        None,
        {f"{DOMAIN}:{SITE_ID}_1001"},
        "hour",
        None,
        {"state", "sum"},
    )
    assert stats == {
        f"{DOMAIN}:{SITE_ID}_1001": [
            {"start": 1735783200.0, "end": 1735786800.0, "state": 11.5, "sum": 11.5},
            {"start": 1735786800.0, "end": 1735790400.0, "state": 25.5, "sum": 37.0},
            {"start": 1735790400.0, "end": 1735794000.0, "state": 29.5, "sum": 66.5},
        ]
    }


async def test_modules_coordinator_subsequent_run_with_gap(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_solar_edge_web: AsyncMock,
) -> None:
    """Test the coordinator correctly updates statistics on subsequent runs with a gap in data."""
    mock_solar_edge_web.async_get_equipment.return_value = {
        1001: {"displayName": "1.1"},
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_SITE_ID: SITE_ID, CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
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

    coordinator: SolarEdgeModulesCoordinator = entry.runtime_data[
        DATA_MODULES_COORDINATOR
    ]
    await _trigger_and_wait_for_refresh(hass, freezer, coordinator)
    await async_wait_recording_done(hass)
    stats = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        dt_util.as_utc(datetime(1970, 1, 1, 0, 0)),
        None,
        {f"{DOMAIN}:{SITE_ID}_1001"},
        "hour",
        None,
        {"state", "sum"},
    )
    assert stats == {
        f"{DOMAIN}:{SITE_ID}_1001": [
            {"start": 1735783200.0, "end": 1735786800.0, "state": 11.5, "sum": 11.5},
            {"start": 1735786800.0, "end": 1735790400.0, "state": 15.5, "sum": 27.0},
            {"start": 1738465200.0, "end": 1738468800.0, "state": 25.5, "sum": 52.5},
        ]
    }


async def test_modules_coordinator_no_energy_data(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_solar_edge_web: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the coordinator handles an empty energy data response from the API."""
    mock_solar_edge_web.async_get_energy_data.return_value = []
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_SITE_ID: SITE_ID, CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert "No data received from SolarEdge API" in caplog.text

    await async_wait_recording_done(hass)
    stats = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        dt_util.as_utc(datetime(1970, 1, 1, 0, 0)),
        None,
        {f"{DOMAIN}:{SITE_ID}_1001", f"{DOMAIN}:{SITE_ID}_1002"},
        "hour",
        None,
        {"state", "sum"},
    )
    assert not stats
