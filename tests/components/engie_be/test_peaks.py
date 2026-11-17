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

from homeassistant.components.engie_be.const import PEAKS_SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import (
    BAN,
    BRUSSELS_TIME_ZONE,
    OFFTAKE_ONLY_EAN,
    advance_time,
    build_monthly_peaks,
    build_monthly_peaks_for_request,
    build_peak,
    get_entity_id,
    get_state,
    setup_entry,
)


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
        hass, entity_registry, "sensor", f"{BAN}_capacity_tariff_monthly_power_peak"
    )
    assert power_state.state == "3.1"
    assert power_state.attributes["peak_month"] == "2026-09"
    assert power_state.attributes["peak_is_fallback"] is True

    start_entity_id = get_entity_id(
        entity_registry, "sensor", f"{BAN}_capacity_tariff_monthly_peak_start"
    )
    assert hass.states.get(start_entity_id).state == "2026-09-20T17:30:00+00:00"


@pytest.mark.usefixtures("frozen_afternoon")
async def test_capacity_tariff_previous_peak_attribute(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the replaced lower peak of the month is exposed as an attribute."""
    current = build_peak(
        datetime(2026, 10, 15, 18, 0, tzinfo=BRUSSELS_TIME_ZONE), power_kw=5.0
    )
    replaced = build_peak(datetime(2026, 10, 3, 12, 0, tzinfo=BRUSSELS_TIME_ZONE))
    peaks_mock = mock_engie_client.return_value.async_get_monthly_peaks
    peaks_mock.side_effect = None
    peaks_mock.return_value = build_monthly_peaks(
        2026, 10, peak=current, previous_peak=replaced
    )
    await setup_entry(hass, mock_config_entry)

    power_state = get_state(
        hass, entity_registry, "sensor", f"{BAN}_capacity_tariff_monthly_power_peak"
    )
    assert power_state.state == "5.0"
    assert power_state.attributes["previous_peak"] == {
        "power_kw": 4.2,
        "energy_kwh": 1.05,
        "start": "2026-10-03T12:00:00+02:00",
        "end": "2026-10-03T12:15:00+02:00",
    }


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
        hass, entity_registry, "sensor", f"{BAN}_capacity_tariff_monthly_power_peak"
    )
    assert power_state.state == "unknown"
    assert power_state.attributes["peak_month"] is None
    assert power_state.attributes["peak_is_fallback"] is False


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
        entity_registry, "sensor", f"{BAN}_capacity_tariff_monthly_power_peak"
    )
    power_state = hass.states.get(power_entity_id)
    assert power_state is not None
    assert power_state.state == "3.3"
    assert power_state.attributes["peak_month"] == "2026-11"
    assert power_state.attributes["peak_is_fallback"] is True

    await advance_time(hass, freezer, timedelta(days=1, seconds=30))

    assert call(BAN, 2027, 1) in peaks_mock.call_args_list
    assert call(BAN, 2026, 12) in peaks_mock.call_args_list
    power_state = hass.states.get(power_entity_id)
    assert power_state is not None
    assert power_state.state == "unknown"
    assert power_state.attributes["peak_month"] is None
    assert power_state.attributes["peak_is_fallback"] is False

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
    assert power_state.attributes["peak_month"] == "2027-01"
    assert power_state.attributes["peak_is_fallback"] is False


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
        entity_registry, "sensor", f"{BAN}_capacity_tariff_monthly_power_peak"
    )
    power_state = hass.states.get(power_entity_id)
    assert power_state is not None
    assert power_state.state == STATE_UNAVAILABLE

    price_state = get_state(
        hass, entity_registry, "sensor", f"{BAN}_{OFFTAKE_ONLY_EAN}_offtake_TOTAL_HOURS"
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
        hass, entity_registry, "sensor", f"{BAN}_capacity_tariff_daily_power_peak"
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
