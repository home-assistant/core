"""Tests for the Opower coordinator, particularly testing merging realtime and cost usage reads."""

from collections.abc import Awaitable, Callable, Generator
from datetime import datetime
from unittest.mock import AsyncMock, patch

from opower import Account, CostRead, MeterType, Opower, UsageRead
from opower.utilities.coned import ConEd
from opower.utilities.enmax import Enmax
import pytest

from homeassistant.components.opower.const import CONF_UTILITY, DOMAIN
from homeassistant.components.opower.coordinator import (
    CONF_PASSWORD,
    CONF_TOTP_SECRET,
    CONF_USERNAME,
    OpowerCoordinator,
)
from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.statistics import get_last_statistics
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest.fixture
def account() -> Account:
    """Fixture to create a test account."""
    return Account(
        customer="",
        uuid="",
        utility_account_id="test_utility_account_id",
        id="",
        meter_type=MeterType.ELEC,
        read_resolution="",
    )


@pytest.fixture
def opower(account: Account) -> Generator[Opower]:
    """Fixture to create a mock Opower instance that lets us mock out API call methods."""
    with patch("homeassistant.components.opower.coordinator.Opower") as opower_mock:
        opower = opower_mock.return_value

        # Mock opower calls used in initial insert statistics run
        opower.async_login = AsyncMock()
        opower.async_get_forecast = AsyncMock()
        opower.utility = ConEd  # ConEd supports realtime usage reads
        opower.async_get_accounts = AsyncMock(return_value=[account])
        opower.async_get_cost_reads = AsyncMock(return_value=[])
        opower.async_get_realtime_usage_reads = AsyncMock(return_value=[])
        yield opower


@pytest.fixture
async def coordinator_factory(
    opower: Opower, recorder_mock: Recorder, hass: HomeAssistant
) -> Callable[[], Awaitable[OpowerCoordinator]]:
    """Fixture that sets up the Opower coordinator and returns it. Returns as a factory function so that we can edit the Opower mock before the coordinator is created."""

    async def factory():
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_UTILITY: "coned",
                CONF_USERNAME: "fake_username",
                CONF_PASSWORD: "fake_password",
                CONF_TOTP_SECRET: "fake_totp_secret",
            },
        )
        entry.add_to_hass(hass)
        assert await async_setup_component(hass, DOMAIN, {})
        return entry.runtime_data

    return factory


async def test_no_realtime_if_not_supported(
    coordinator_factory: Callable[[], Awaitable[OpowerCoordinator]],
    account: Account,
    opower: Opower,
    hass: HomeAssistant,
) -> None:
    """Test that we only fetch cost reads if the utility does not support realtime reads."""
    opower.utility = Enmax  # Enmax does not support realtime usage reads
    del opower.async_get_realtime_usage_reads  # Should throw error if called
    opower.async_get_cost_reads = AsyncMock(
        return_value=[
            CostRead(
                start_time=datetime.fromisoformat("2020-01-01T00:00Z"),
                end_time=datetime.fromisoformat("2020-01-01T01:00Z"),
                consumption=2,
                provided_cost=0,
            )
        ]
    )
    coordinator = await coordinator_factory()
    statistics_id = coordinator._consumption_statistic_id(account)
    statistics = get_last_statistics(
        hass,
        100,
        statistics_id,
        False,
        {"sum"},
    )[statistics_id]
    assert statistics == [
        {
            "start": datetime.fromisoformat("2020-01-01T00:00Z").timestamp(),
            "end": datetime.fromisoformat("2020-01-01T01:00Z").timestamp(),
            "sum": 2.0,
        }
    ]


async def test_only_realtime(
    coordinator_factory: Callable[[], Awaitable[OpowerCoordinator]],
    account: Account,
    opower: Opower,
    hass: HomeAssistant,
) -> None:
    """Test that 15 minute realtime intervals get aggregated into hourly stats."""
    opower.async_get_realtime_usage_reads = AsyncMock(
        return_value=[
            # Add four distinct values for 15 minute intervals of first hour.
            UsageRead(
                start_time=datetime.fromisoformat("2020-01-01T00:00Z"),
                end_time=datetime.fromisoformat("2020-01-01T00:15Z"),
                consumption=1,
            ),
            UsageRead(
                start_time=datetime.fromisoformat("2020-01-01T00:15Z"),
                end_time=datetime.fromisoformat("2020-01-01T00:30Z"),
                consumption=10,
            ),
            UsageRead(
                start_time=datetime.fromisoformat("2020-01-01T00:30Z"),
                end_time=datetime.fromisoformat("2020-01-01T00:45Z"),
                consumption=100,
            ),
            UsageRead(
                start_time=datetime.fromisoformat("2020-01-01T00:45Z"),
                end_time=datetime.fromisoformat("2020-01-01T01:00Z"),
                consumption=1000,
            ),
            # Add another value in the next hour.
            UsageRead(
                start_time=datetime.fromisoformat("2020-01-01T01:00Z"),
                end_time=datetime.fromisoformat("2020-01-01T01:15Z"),
                consumption=2,
            ),
        ]
    )
    coordinator = await coordinator_factory()
    statistics_id = coordinator._consumption_statistic_id(account)
    statistics = get_last_statistics(
        hass,
        100,
        statistics_id,
        False,
        {"sum"},
    )[statistics_id]
    assert statistics == [
        {
            "start": datetime.fromisoformat("2020-01-01T01:00Z").timestamp(),
            "end": datetime.fromisoformat("2020-01-01T02:00Z").timestamp(),
            "sum": 1113.0,
        },
        {
            "start": datetime.fromisoformat("2020-01-01T00:00Z").timestamp(),
            "end": datetime.fromisoformat("2020-01-01T01:00Z").timestamp(),
            "sum": 1111.0,
        },
    ]


async def test_merged_reads_interleaved(
    coordinator_factory: Callable[[], Awaitable[OpowerCoordinator]],
    account: Account,
    opower: Opower,
    hass: HomeAssistant,
) -> None:
    """We can have cost data interleaved with realtime data. In this test, we have hour 0 cost, hour 1 realtime, hour 2 cost."""
    opower.async_get_realtime_usage_reads = AsyncMock(
        return_value=[
            UsageRead(
                start_time=datetime.fromisoformat("2020-01-01T01:00Z"),
                end_time=datetime.fromisoformat("2020-01-01T01:15Z"),
                consumption=1,
            ),
            UsageRead(
                start_time=datetime.fromisoformat("2020-01-01T01:15Z"),
                end_time=datetime.fromisoformat("2020-01-01T01:30Z"),
                consumption=10,
            ),
        ]
    )
    opower.async_get_cost_reads = AsyncMock(
        return_value=[
            CostRead(
                start_time=datetime.fromisoformat("2020-01-01T00:00Z"),
                end_time=datetime.fromisoformat("2020-01-01T01:00Z"),
                consumption=2,
                provided_cost=0,
            ),
            CostRead(
                start_time=datetime.fromisoformat("2020-01-01T02:00Z"),
                end_time=datetime.fromisoformat("2020-01-01T03:00Z"),
                consumption=20,
                provided_cost=0,
            ),
        ]
    )
    coordinator = await coordinator_factory()
    statistics_id = coordinator._consumption_statistic_id(account)
    statistics = get_last_statistics(
        hass,
        100,
        statistics_id,
        False,
        {"sum"},
    )[statistics_id]
    assert statistics == [
        {
            "start": datetime.fromisoformat("2020-01-01T02:00Z").timestamp(),
            "end": datetime.fromisoformat("2020-01-01T03:00Z").timestamp(),
            "sum": 33.0,
        },
        {
            "start": datetime.fromisoformat("2020-01-01T01:00Z").timestamp(),
            "end": datetime.fromisoformat("2020-01-01T02:00Z").timestamp(),
            "sum": 13.0,
        },
        {
            "start": datetime.fromisoformat("2020-01-01T00:00Z").timestamp(),
            "end": datetime.fromisoformat("2020-01-01T01:00Z").timestamp(),
            "sum": 2.0,
        },
    ]


async def test_merged_reads_prioritizes_cost_reads(
    coordinator_factory: Callable[[], Awaitable[OpowerCoordinator]],
    account: Account,
    opower: Opower,
    hass: HomeAssistant,
) -> None:
    """Test that cost reads are prioritized over realtime reads."""
    opower.async_get_realtime_usage_reads = AsyncMock(
        return_value=[
            UsageRead(
                start_time=datetime.fromisoformat("2020-01-01T00:00Z"),
                end_time=datetime.fromisoformat("2020-01-01T00:15Z"),
                consumption=1,
            )
        ]
    )
    opower.async_get_cost_reads = AsyncMock(
        return_value=[
            CostRead(
                start_time=datetime.fromisoformat("2020-01-01T00:00Z"),
                end_time=datetime.fromisoformat("2020-01-01T01:00Z"),
                consumption=2,
                provided_cost=0,
            )
        ]
    )
    coordinator = await coordinator_factory()
    statistics_id = coordinator._consumption_statistic_id(account)
    statistics = get_last_statistics(
        hass,
        100,
        statistics_id,
        False,
        {"sum"},
    )[statistics_id]
    assert statistics == [
        {
            "start": datetime.fromisoformat("2020-01-01T00:00Z").timestamp(),
            "end": datetime.fromisoformat("2020-01-01T01:00Z").timestamp(),
            "sum": 2.0,
        }
    ]
