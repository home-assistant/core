"""Tests for the SolarEdge coordinator services."""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from aiohttp import ClientError
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.components.recorder.common import async_wait_recording_done
from solaredge_web import EnergyData

from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    async_list_statistic_ids,
    statistics_during_period,
)
from homeassistant.components.solaredge.const import (
    CONF_SITE_ID,
    DATA_MODULES_COORDINATOR,
    DEFAULT_NAME,
    DOMAIN,
    OVERVIEW_UPDATE_DELAY,
    POWER_FLOW_UPDATE_DELAY,
)
from homeassistant.components.solaredge.coordinator import SolarEdgeModulesCoordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_API_KEY,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    STATE_UNKNOWN,
    UnitOfEnergy,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import EnergyConverter

from . import setup_integration
from .conftest import API_KEY, PASSWORD, SITE_ID, USERNAME


@pytest.fixture(autouse=True)
def enable_all_entities(entity_registry_enabled_by_default: None) -> None:
    """Make sure all entities are enabled."""


@patch("homeassistant.components.solaredge.SolarEdge")
async def test_solaredgeoverviewdataservice_energy_values_validity(
    mock_solaredge: MagicMock,
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


async def test_power_flow_null_response(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    solaredge_api: Mock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a null power flow response raises UpdateFailed, not TypeError.

    The API returns "siteCurrentPowerFlow": null for sites without
    power flow reporting. Regression test for
    https://github.com/home-assistant/core/issues/188399 .
    """
    await setup_integration(hass, mock_config_entry)

    solaredge_api.get_current_power_flow = AsyncMock(
        return_value={"siteCurrentPowerFlow": None}
    )

    freezer.tick(POWER_FLOW_UPDATE_DELAY)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert "Missing power flow data, skipping update" in caplog.text
    assert "Unexpected error" not in caplog.text


async def _trigger_and_wait_for_refresh(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    coordinator: SolarEdgeModulesCoordinator,
) -> None:
    """Trigger a coordinator refresh and wait for it to complete."""
    # The coordinator refresh runs in the background.
    # To reliably assert the result, we need to wait for the refresh to complete.
    # We patch the coordinator's update method to signal completion
    # via an asyncio.Event.
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
            "7A012345-CA": {"name": "Optimizer 1.1", "type": "OPTIMIZER"},
            "7A012346-CA": {"name": "Optimizer 1.2", "type": "OPTIMIZER"},
        }
        api.async_get_energy_data.return_value = [
            EnergyData(
                start_time=dt_util.as_utc(datetime(2025, 1, 1, 10, 0)),
                values={"7A012345-CA": 10.0, "7A012346-CA": 20.0},
            ),
            EnergyData(
                start_time=dt_util.as_utc(datetime(2025, 1, 1, 11, 0)),
                values={"7A012345-CA": 14.0, "7A012346-CA": 24.0},
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
        {f"{DOMAIN}:{SITE_ID}_7a012345_ca", f"{DOMAIN}:{SITE_ID}_7a012346_ca"},
        "hour",
        None,
        {"state", "sum"},
    )
    assert stats == {
        f"{DOMAIN}:{SITE_ID}_7a012345_ca": [
            {"start": 1735783200.0, "end": 1735786800.0, "state": 10.0, "sum": 10.0},
            {"start": 1735786800.0, "end": 1735790400.0, "state": 14.0, "sum": 24.0},
        ],
        f"{DOMAIN}:{SITE_ID}_7a012346_ca": [
            {"start": 1735783200.0, "end": 1735786800.0, "state": 20.0, "sum": 20.0},
            {"start": 1735786800.0, "end": 1735790400.0, "state": 24.0, "sum": 44.0},
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
        "7A012345-CA": {"name": "Optimizer 1.1", "type": "OPTIMIZER"},
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
            values={"7A012345-CA": 24.0},
        ),
        # New values for the next hour
        EnergyData(
            start_time=dt_util.as_utc(datetime(2025, 1, 1, 12, 0)),
            values={"7A012345-CA": 28.0},
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
        {f"{DOMAIN}:{SITE_ID}_7a012345_ca"},
        "hour",
        None,
        {"state", "sum"},
    )
    assert stats == {
        f"{DOMAIN}:{SITE_ID}_7a012345_ca": [
            {"start": 1735783200.0, "end": 1735786800.0, "state": 10.0, "sum": 10.0},
            {"start": 1735786800.0, "end": 1735790400.0, "state": 24.0, "sum": 34.0},
            {"start": 1735790400.0, "end": 1735794000.0, "state": 28.0, "sum": 62.0},
        ]
    }


async def test_modules_coordinator_subsequent_run_with_gap(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_solar_edge_web: AsyncMock,
) -> None:
    """Test the coordinator updates statistics with a gap in data."""
    mock_solar_edge_web.async_get_equipment.return_value = {
        "7A012345-CA": {"name": "Optimizer 1.1", "type": "OPTIMIZER"},
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
            values={"7A012345-CA": 24.0},
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
        {f"{DOMAIN}:{SITE_ID}_7a012345_ca"},
        "hour",
        None,
        {"state", "sum"},
    )
    assert stats == {
        f"{DOMAIN}:{SITE_ID}_7a012345_ca": [
            {"start": 1735783200.0, "end": 1735786800.0, "state": 10.0, "sum": 10.0},
            {"start": 1735786800.0, "end": 1735790400.0, "state": 14.0, "sum": 24.0},
            {"start": 1738465200.0, "end": 1738468800.0, "state": 24.0, "sum": 48.0},
        ]
    }


async def test_modules_coordinator_reprocess_same_window_after_gap(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_solar_edge_web: AsyncMock,
) -> None:
    """Test the sum doesn't reset when the same window is refreshed again.

    After a gap the window is filled starting from the last sum before it. A
    later refresh of the same window, e.g. after reloading the integration the
    same day, must keep continuing from that sum. The window is taken from the
    energy data returned by the API, so the gap is simulated by moving the
    returned data instead of the clock.

    Regression test for https://github.com/home-assistant/core/issues/186653 .
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_SITE_ID: SITE_ID, CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    coordinator: SolarEdgeModulesCoordinator = entry.runtime_data[
        DATA_MODULES_COORDINATOR
    ]

    # Values a month later, simulating a gap in data. The first row is also
    # exactly at the start of the window, with older statistics before it.
    mock_solar_edge_web.async_get_energy_data.return_value = [
        EnergyData(
            start_time=dt_util.as_utc(datetime(2025, 2, 1, 11, 0)),
            values={"7A012345-CA": 24.0, "7A012346-CA": 30.0},
        ),
    ]
    await _trigger_and_wait_for_refresh(hass, freezer, coordinator)
    await async_wait_recording_done(hass)

    # Refresh the same window again, e.g. after reloading the integration the
    # same day. The sums must not reset to 0.
    await _trigger_and_wait_for_refresh(hass, freezer, coordinator)
    await async_wait_recording_done(hass)

    stats = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        dt_util.as_utc(datetime(1970, 1, 1, 0, 0)),
        None,
        {f"{DOMAIN}:{SITE_ID}_7a012345_ca", f"{DOMAIN}:{SITE_ID}_7a012346_ca"},
        "hour",
        None,
        {"state", "sum"},
    )
    assert stats == {
        f"{DOMAIN}:{SITE_ID}_7a012345_ca": [
            {"start": 1735783200.0, "end": 1735786800.0, "state": 10.0, "sum": 10.0},
            {"start": 1735786800.0, "end": 1735790400.0, "state": 14.0, "sum": 24.0},
            {"start": 1738465200.0, "end": 1738468800.0, "state": 24.0, "sum": 48.0},
        ],
        f"{DOMAIN}:{SITE_ID}_7a012346_ca": [
            {"start": 1735783200.0, "end": 1735786800.0, "state": 20.0, "sum": 20.0},
            {"start": 1735786800.0, "end": 1735790400.0, "state": 24.0, "sum": 44.0},
            {"start": 1738465200.0, "end": 1738468800.0, "state": 30.0, "sum": 74.0},
        ],
    }


async def test_modules_coordinator_reprocess_same_window_new_equipment(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_solar_edge_web: AsyncMock,
) -> None:
    """Test reprocessing the same window with a newly added optimizer.

    The optimizer that already has statistics continues from the last sum before
    the window, while the newly added one, which has no earlier statistics,
    starts from 0.
    """
    mock_solar_edge_web.async_get_equipment.return_value = {
        "7A012345-CA": {"name": "Optimizer 1.1", "type": "OPTIMIZER"},
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_SITE_ID: SITE_ID, CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    coordinator: SolarEdgeModulesCoordinator = entry.runtime_data[
        DATA_MODULES_COORDINATOR
    ]

    # A second optimizer is added a month later, after a gap in the data.
    mock_solar_edge_web.async_get_equipment.return_value = {
        "7A012345-CA": {"name": "Optimizer 1.1", "type": "OPTIMIZER"},
        "7A012346-CA": {"name": "Optimizer 1.2", "type": "OPTIMIZER"},
    }
    mock_solar_edge_web.async_get_energy_data.return_value = [
        EnergyData(
            start_time=dt_util.as_utc(datetime(2025, 2, 1, 11, 0)),
            values={"7A012345-CA": 24.0, "7A012346-CA": 30.0},
        ),
    ]
    await _trigger_and_wait_for_refresh(hass, freezer, coordinator)
    await async_wait_recording_done(hass)

    # Refresh the same window again, e.g. after reloading the integration the
    # same day.
    await _trigger_and_wait_for_refresh(hass, freezer, coordinator)
    await async_wait_recording_done(hass)

    stats = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        dt_util.as_utc(datetime(1970, 1, 1, 0, 0)),
        None,
        {f"{DOMAIN}:{SITE_ID}_7a012345_ca", f"{DOMAIN}:{SITE_ID}_7a012346_ca"},
        "hour",
        None,
        {"state", "sum"},
    )
    assert stats == {
        f"{DOMAIN}:{SITE_ID}_7a012345_ca": [
            {"start": 1735783200.0, "end": 1735786800.0, "state": 10.0, "sum": 10.0},
            {"start": 1735786800.0, "end": 1735790400.0, "state": 14.0, "sum": 24.0},
            {"start": 1738465200.0, "end": 1738468800.0, "state": 24.0, "sum": 48.0},
        ],
        f"{DOMAIN}:{SITE_ID}_7a012346_ca": [
            {"start": 1738465200.0, "end": 1738468800.0, "state": 30.0, "sum": 30.0},
        ],
    }


async def test_modules_coordinator_first_window_statistic_without_sum(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_solar_edge_web: AsyncMock,
) -> None:
    """Test the sum is still recovered when the first in-window statistic has no sum.

    The recorder computes the change relative to the last sum before the window,
    so the first in-window statistic that has a sum recovers the baseline even
    when preceding statistics in the window have none.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_SITE_ID: SITE_ID, CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    statistic_id = f"{DOMAIN}:{SITE_ID}_7a012345_ca"
    # The first statistic in the window has no sum, the next one does. Its sum
    # of 34 equals the 24 from the last statistic before the window plus 10.
    async_add_external_statistics(
        hass,
        StatisticMetaData(
            mean_type=StatisticMeanType.ARITHMETIC,
            has_sum=True,
            name=f"{entry.title} Optimizer 1.1",
            source=DOMAIN,
            statistic_id=statistic_id,
            unit_class=EnergyConverter.UNIT_CLASS,
            unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        ),
        [
            StatisticData(
                start=dt_util.as_utc(datetime(2025, 2, 1, 11, 0)).replace(
                    tzinfo=dt_util.get_default_time_zone()
                ),
                state=None,
                sum=None,
            ),
            StatisticData(
                start=dt_util.as_utc(datetime(2025, 2, 1, 12, 0)).replace(
                    tzinfo=dt_util.get_default_time_zone()
                ),
                state=10.0,
                sum=34.0,
            ),
        ],
    )
    await async_wait_recording_done(hass)

    mock_solar_edge_web.async_get_energy_data.return_value = [
        EnergyData(
            start_time=dt_util.as_utc(datetime(2025, 2, 1, 11, 0)),
            values={"7A012345-CA": 10.0},
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
        {statistic_id},
        "hour",
        None,
        {"state", "sum"},
    )
    assert stats == {
        statistic_id: [
            {"start": 1735783200.0, "end": 1735786800.0, "state": 10.0, "sum": 10.0},
            {"start": 1735786800.0, "end": 1735790400.0, "state": 14.0, "sum": 24.0},
            {"start": 1738465200.0, "end": 1738468800.0, "state": 10.0, "sum": 34.0},
            {"start": 1738468800.0, "end": 1738472400.0, "state": 10.0, "sum": 34.0},
        ]
    }


async def test_modules_coordinator_window_statistics_without_sum(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_solar_edge_web: AsyncMock,
) -> None:
    """Test the sum is recovered when no in-window statistic has a sum.

    With no usable sum in the window, the baseline must come from the last
    statistic before the window rather than from the last in-window statistic.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_SITE_ID: SITE_ID, CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    statistic_id = f"{DOMAIN}:{SITE_ID}_7a012345_ca"
    # Every statistic in the window has no sum.
    async_add_external_statistics(
        hass,
        StatisticMetaData(
            mean_type=StatisticMeanType.ARITHMETIC,
            has_sum=True,
            name=f"{entry.title} Optimizer 1.1",
            source=DOMAIN,
            statistic_id=statistic_id,
            unit_class=EnergyConverter.UNIT_CLASS,
            unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        ),
        [
            StatisticData(
                start=dt_util.as_utc(datetime(2025, 2, 1, hour, 0)).replace(
                    tzinfo=dt_util.get_default_time_zone()
                ),
                state=None,
                sum=None,
            )
            for hour in (11, 12)
        ],
    )
    await async_wait_recording_done(hass)

    mock_solar_edge_web.async_get_energy_data.return_value = [
        EnergyData(
            start_time=dt_util.as_utc(datetime(2025, 2, 1, 11, 0)),
            values={"7A012345-CA": 10.0},
        ),
        EnergyData(
            start_time=dt_util.as_utc(datetime(2025, 2, 1, 12, 0)),
            values={"7A012345-CA": 5.0},
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
        {statistic_id},
        "hour",
        None,
        {"state", "sum"},
    )
    assert stats == {
        statistic_id: [
            {"start": 1735783200.0, "end": 1735786800.0, "state": 10.0, "sum": 10.0},
            {"start": 1735786800.0, "end": 1735790400.0, "state": 14.0, "sum": 24.0},
            {"start": 1738465200.0, "end": 1738468800.0, "state": 10.0, "sum": 34.0},
            {"start": 1738468800.0, "end": 1738472400.0, "state": 5.0, "sum": 39.0},
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
        {f"{DOMAIN}:{SITE_ID}_7a012345_ca", f"{DOMAIN}:{SITE_ID}_7a012346_ca"},
        "hour",
        None,
        {"state", "sum"},
    )
    assert not stats


async def test_modules_coordinator_api_failure(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry_web_login: MockConfigEntry,
    solaredge_web_api: AsyncMock,
) -> None:
    """Test the modules coordinator surfaces API failures via the config entry state."""
    solaredge_web_api.async_get_equipment.side_effect = ClientError("boom")

    await setup_integration(hass, mock_config_entry_web_login)

    assert mock_config_entry_web_login.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("recorder_mock")
async def test_legacy_statistic_id_reused(
    hass: HomeAssistant,
    mock_solar_edge_web: AsyncMock,
) -> None:
    """Test that legacy numeric statistic IDs are reused via name matching."""
    # Add a legacy numeric statistic with name "1.1" (matching equipment name).
    legacy_statistic_id = f"{DOMAIN}:{SITE_ID}_231397259"
    legacy_metadata = StatisticMetaData(
        mean_type=StatisticMeanType.ARITHMETIC,
        has_sum=True,
        name="SolarEdge 1.1",
        source=DOMAIN,
        statistic_id=legacy_statistic_id,
        unit_class=EnergyConverter.UNIT_CLASS,
        unit_of_measurement="Wh",
    )
    async_add_external_statistics(hass, legacy_metadata, [])
    await async_wait_recording_done(hass)

    # Equipment with matching name "1.1".
    mock_solar_edge_web.async_get_equipment.return_value = {
        "7A012345-CA": {"name": "Optimizer 1.1", "type": "OPTIMIZER"},
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="SolarEdge",
        data={CONF_SITE_ID: SITE_ID, CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    # The legacy statistic ID should be reused (not a new serial-based one).
    coordinator: SolarEdgeModulesCoordinator = entry.runtime_data[
        DATA_MODULES_COORDINATOR
    ]
    assert coordinator.get_statistic_id("7A012345-CA") == legacy_statistic_id

    # Data should be inserted under the legacy ID.
    stats = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        dt_util.as_utc(datetime(1970, 1, 1, 0, 0)),
        None,
        {legacy_statistic_id},
        "hour",
        None,
        {"state", "sum"},
    )
    assert stats == {
        legacy_statistic_id: [
            {"start": 1735783200.0, "end": 1735786800.0, "state": 10.0, "sum": 10.0},
            {"start": 1735786800.0, "end": 1735790400.0, "state": 14.0, "sum": 24.0},
        ]
    }
    # No new serial-based ID should have been created.
    all_stats = await async_list_statistic_ids(hass)
    stat_ids = {s["statistic_id"] for s in all_stats}
    assert f"{DOMAIN}:{SITE_ID}_7a012345_ca" not in stat_ids


@pytest.mark.usefixtures("recorder_mock")
async def test_legacy_statistic_id_ambiguous(
    hass: HomeAssistant,
    mock_solar_edge_web: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that ambiguous legacy statistic names are not reused."""
    # Two legacy numeric statistics with the same name, e.g. after a module
    # replacement created a new series under a new numeric ID.
    for legacy_id in (
        f"{DOMAIN}:{SITE_ID}_231397259",
        f"{DOMAIN}:{SITE_ID}_231397260",
    ):
        legacy_metadata = StatisticMetaData(
            mean_type=StatisticMeanType.ARITHMETIC,
            has_sum=True,
            name="SolarEdge 1.1",
            source=DOMAIN,
            statistic_id=legacy_id,
            unit_class=EnergyConverter.UNIT_CLASS,
            unit_of_measurement="Wh",
        )
        async_add_external_statistics(hass, legacy_metadata, [])
    await async_wait_recording_done(hass)

    # Equipment with matching name "1.1".
    mock_solar_edge_web.async_get_equipment.return_value = {
        "7A012345-CA": {"name": "Optimizer 1.1", "type": "OPTIMIZER"},
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="SolarEdge",
        data={CONF_SITE_ID: SITE_ID, CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    # The match is ambiguous, so a new serial-based ID is used.
    coordinator: SolarEdgeModulesCoordinator = entry.runtime_data[
        DATA_MODULES_COORDINATOR
    ]
    assert (
        coordinator.get_statistic_id("7A012345-CA") == f"{DOMAIN}:{SITE_ID}_7a012345_ca"
    )
    assert "ambiguous" in caplog.text


@pytest.mark.usefixtures("recorder_mock")
async def test_modules_coordinator_skips_non_pv_equipment(
    hass: HomeAssistant,
    mock_solar_edge_web: AsyncMock,
) -> None:
    """Test that non-PV equipment such as batteries is skipped.

    Battery modules share the same positional short names (e.g. "1.1.1") as
    optimizers. If not filtered out, they map to the same legacy statistic IDs
    and overwrite the optimizer statistics with zero values.
    """
    legacy_statistic_id = f"{DOMAIN}:{SITE_ID}_310549011"
    legacy_metadata = StatisticMetaData(
        mean_type=StatisticMeanType.ARITHMETIC,
        has_sum=True,
        name="SolarEdge Battery Module 1.1.1",
        source=DOMAIN,
        statistic_id=legacy_statistic_id,
        unit_class=EnergyConverter.UNIT_CLASS,
        unit_of_measurement="Wh",
    )
    async_add_external_statistics(hass, legacy_metadata, [])
    await async_wait_recording_done(hass)

    mock_solar_edge_web.async_get_equipment.return_value = {
        "7E012345-57": {"name": "Inverter 1", "type": "INVERTER"},
        "7E012345_31": {"name": "String 1.1", "type": "STRING"},
        "7A012345-CA": {"name": "Optimizer 1.1.1", "type": "OPTIMIZER"},
        "BAT-PACK-01": {"name": "Battery 1.1", "type": "BATTERY"},
        "BAT-MOD-01": {"name": "Battery Module 1.1.1", "type": "BATTERY_MODULE"},
    }
    mock_solar_edge_web.async_get_energy_data.return_value = [
        EnergyData(
            start_time=dt_util.as_utc(datetime(2025, 1, 1, 10, 0)),
            values={
                "7E012345-57": 10.0,
                "7E012345_31": 10.0,
                "7A012345-CA": 10.0,
            },
        ),
        EnergyData(
            start_time=dt_util.as_utc(datetime(2025, 1, 1, 11, 0)),
            values={
                "7E012345-57": 14.0,
                "7E012345_31": 14.0,
                "7A012345-CA": 14.0,
            },
        ),
    ]

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="SolarEdge",
        data={CONF_SITE_ID: SITE_ID, CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    # Optimizer 1.1.1 reuses the legacy statistic ID without being overwritten
    # by Battery Module 1.1.1, and its metadata name is updated to the
    # optimizer's.
    stats = await hass.async_add_executor_job(
        statistics_during_period,
        hass,
        dt_util.as_utc(datetime(1970, 1, 1, 0, 0)),
        None,
        {legacy_statistic_id},
        "hour",
        None,
        {"state", "sum"},
    )
    assert stats == {
        legacy_statistic_id: [
            {"start": 1735783200.0, "end": 1735786800.0, "state": 10.0, "sum": 10.0},
            {"start": 1735786800.0, "end": 1735790400.0, "state": 14.0, "sum": 24.0},
        ]
    }

    all_stats = await async_list_statistic_ids(hass)
    stats_by_id = {s["statistic_id"]: s["name"] for s in all_stats}
    assert stats_by_id == {
        f"{DOMAIN}:{SITE_ID}_7e012345_57": "SolarEdge Inverter 1",
        f"{DOMAIN}:{SITE_ID}_7e012345_31": "SolarEdge String 1.1",
        legacy_statistic_id: "SolarEdge Optimizer 1.1.1",
    }
