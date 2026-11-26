"""Test the ENGIE Belgium capacity tariff peak sensors."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, call

from aioengiebelgium import (
    EngieBeAuthenticationError,
    EngieBeCommunicationError,
    MonthlyPeaks,
    Peak,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.engie_be.const import (
    BRUSSELS_TIME_ZONE,
    PEAKS_SCAN_INTERVAL,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import (
    BAN,
    OFFTAKE_TOTAL_HOURS_UNIQUE_ID,
    advance_time,
    build_monthly_peaks,
    build_monthly_peaks_for_request,
    build_peak,
    get_entity_id,
    get_state,
    setup_entry,
)

MONTHLY_POWER_PEAK_UNIQUE_ID = f"{BAN}_capacity_tariff_monthly_power_peak"


@pytest.mark.usefixtures("mock_engie_client", "frozen_afternoon")
@pytest.mark.parametrize(
    "key",
    [
        "capacity_tariff_monthly_power_peak",
        "capacity_tariff_monthly_energy_peak",
        "capacity_tariff_monthly_peak_start",
        "capacity_tariff_monthly_peak_end",
        "capacity_tariff_daily_power_peak",
    ],
)
async def test_capacity_tariff_sensors_enabled_by_default(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    key: str,
) -> None:
    """Test the capacity tariff sensors are enabled by default."""
    await setup_entry(hass, mock_config_entry)

    entity_id = get_entity_id(entity_registry, Platform.SENSOR, f"{BAN}_{key}")
    entry = entity_registry.async_get(entity_id)
    assert entry is not None
    assert entry.disabled_by is None


@pytest.mark.usefixtures("frozen_afternoon")
async def test_capacity_tariff_fallback_to_previous_month(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the sensors show the previous month's peak until this month has one."""
    september_peak = build_peak(
        datetime(2026, 9, 20, 19, 30, tzinfo=BRUSSELS_TIME_ZONE), power_kw=3.1
    )

    def _peaks(ban: str, year: int, month: int) -> MonthlyPeaks:
        if (year, month) == (2026, 10):
            return build_monthly_peaks(2026, 10)
        return build_monthly_peaks(2026, 9, peak=september_peak)

    mock_engie_client.return_value.async_get_monthly_peaks.side_effect = _peaks
    await setup_entry(hass, mock_config_entry)

    power_state = get_state(
        hass, entity_registry, Platform.SENSOR, MONTHLY_POWER_PEAK_UNIQUE_ID
    )
    assert power_state.state == "3.1"

    start_entity_id = get_entity_id(
        entity_registry, Platform.SENSOR, f"{BAN}_capacity_tariff_monthly_peak_start"
    )
    assert hass.states.get(start_entity_id).state == "2026-09-20T17:30:00+00:00"


@pytest.mark.usefixtures("frozen_afternoon")
async def test_capacity_tariff_no_peak_yet(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the sensors are unknown when neither month has a peak."""
    mock_engie_client.return_value.async_get_monthly_peaks.side_effect = (
        lambda ban, year, month: build_monthly_peaks(year, month)
    )
    await setup_entry(hass, mock_config_entry)

    power_state = get_state(
        hass, entity_registry, Platform.SENSOR, MONTHLY_POWER_PEAK_UNIQUE_ID
    )
    assert power_state.state == "unknown"


async def test_capacity_tariff_scheduled_refresh_across_year_rollover(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a scheduled refresh in January falls back to December of the previous year."""
    freezer.move_to(datetime(2026, 12, 31, 14, 0, tzinfo=BRUSSELS_TIME_ZONE))
    november_peak = build_peak(
        datetime(2026, 11, 18, 19, 0, tzinfo=BRUSSELS_TIME_ZONE), power_kw=3.3
    )

    def _peaks(ban: str, year: int, month: int) -> MonthlyPeaks:
        if (year, month) == (2026, 11):
            return build_monthly_peaks(2026, 11, peak=november_peak)
        return build_monthly_peaks(year, month)

    peaks_mock = mock_engie_client.return_value.async_get_monthly_peaks
    peaks_mock.side_effect = _peaks
    await setup_entry(hass, mock_config_entry)

    power_entity_id = get_entity_id(
        entity_registry, Platform.SENSOR, MONTHLY_POWER_PEAK_UNIQUE_ID
    )
    power_state = hass.states.get(power_entity_id)
    assert power_state is not None
    assert power_state.state == "3.3"

    await advance_time(hass, freezer, timedelta(days=1, seconds=30))

    assert call(BAN, 2027, 1) in peaks_mock.call_args_list
    assert call(BAN, 2026, 12) in peaks_mock.call_args_list
    power_state = hass.states.get(power_entity_id)
    assert power_state is not None
    assert power_state.state == "unknown"

    january_peak = build_peak(
        datetime(2027, 1, 10, 18, 30, tzinfo=BRUSSELS_TIME_ZONE), power_kw=5.1
    )

    def _peaks_with_january(ban: str, year: int, month: int) -> MonthlyPeaks:
        if (year, month) == (2027, 1):
            return build_monthly_peaks(
                2027, 1, peak=january_peak, daily_peaks=(january_peak,)
            )
        return _peaks(ban, year, month)

    peaks_mock.side_effect = _peaks_with_january
    await advance_time(hass, freezer, PEAKS_SCAN_INTERVAL + timedelta(seconds=30))

    power_state = hass.states.get(power_entity_id)
    assert power_state is not None
    assert power_state.state == "5.1"


@pytest.mark.usefixtures("frozen_afternoon")
async def test_capacity_tariff_peaks_failure_and_recovery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test capacity tariff sensors go unavailable on peaks-endpoint failure and recover on the next poll."""
    peaks_mock = mock_engie_client.return_value.async_get_monthly_peaks
    peaks_mock.side_effect = EngieBeCommunicationError("boom")
    await setup_entry(hass, mock_config_entry)

    power_entity_id = get_entity_id(
        entity_registry, Platform.SENSOR, MONTHLY_POWER_PEAK_UNIQUE_ID
    )
    power_state = hass.states.get(power_entity_id)
    assert power_state is not None
    assert power_state.state == STATE_UNAVAILABLE

    price_state = get_state(
        hass, entity_registry, Platform.SENSOR, OFFTAKE_TOTAL_HOURS_UNIQUE_ID
    )
    assert price_state.state == "0.123456"

    peaks_mock.side_effect = None
    peaks_mock.return_value = build_monthly_peaks_for_request(BAN, 2026, 10)
    await advance_time(hass, freezer, PEAKS_SCAN_INTERVAL + timedelta(seconds=30))
    power_state = hass.states.get(power_entity_id)
    assert power_state is not None
    assert power_state.state == "4.2"

    peaks_mock.side_effect = EngieBeCommunicationError("boom")
    await advance_time(hass, freezer, PEAKS_SCAN_INTERVAL + timedelta(seconds=30))
    power_state = hass.states.get(power_entity_id)
    assert power_state is not None
    assert power_state.state == STATE_UNAVAILABLE

    peaks_mock.side_effect = None
    await advance_time(hass, freezer, PEAKS_SCAN_INTERVAL + timedelta(seconds=30))
    power_state = hass.states.get(power_entity_id)
    assert power_state is not None
    assert power_state.state == "4.2"


@pytest.mark.usefixtures("frozen_afternoon")
@pytest.mark.parametrize(
    ("daily_peaks", "expected_state"),
    [
        pytest.param(
            (
                build_peak(
                    datetime(2026, 10, 3, 12, 0, tzinfo=BRUSSELS_TIME_ZONE),
                    power_kw=5.0,
                ),
                build_peak(
                    datetime(2026, 10, 10, 18, 0, tzinfo=BRUSSELS_TIME_ZONE),
                    power_kw=4.0,
                ),
            ),
            "4.0",
            id="latest-by-start-not-highest-power",
        ),
        pytest.param((), "unknown", id="empty-daily-peaks"),
    ],
)
async def test_capacity_tariff_daily_peak_selection(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    daily_peaks: tuple[Peak, ...],
    expected_state: str,
) -> None:
    """Test the daily peak sensor picks the latest peak by start and handles an empty list."""
    month_peak = build_peak(datetime(2026, 10, 15, 18, 0, tzinfo=BRUSSELS_TIME_ZONE))
    peaks_mock = mock_engie_client.return_value.async_get_monthly_peaks
    peaks_mock.side_effect = None
    peaks_mock.return_value = build_monthly_peaks(
        2026, 10, peak=month_peak, daily_peaks=daily_peaks
    )
    await setup_entry(hass, mock_config_entry)

    daily_state = get_state(
        hass,
        entity_registry,
        Platform.SENSOR,
        f"{BAN}_capacity_tariff_daily_power_peak",
    )
    assert daily_state.state == expected_state


@pytest.mark.usefixtures("frozen_afternoon")
async def test_capacity_tariff_auth_error_triggers_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
) -> None:
    """Test an authentication error on the peaks endpoint starts reauthentication."""
    mock_engie_client.return_value.async_get_monthly_peaks.side_effect = (
        EngieBeAuthenticationError("expired")
    )
    await setup_entry(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    flows = hass.config_entries.flow.async_progress()
    assert any(flow["context"].get("source") == "reauth" for flow in flows)
