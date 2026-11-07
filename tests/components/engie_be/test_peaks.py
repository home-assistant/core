"""Test the ENGIE Belgium capacity-tariff (captar) peak sensors."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, call

from aioengiebelgium import EngieBeAuthenticationError
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.engie_be.const import DOMAIN, PEAKS_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import (
    BAN,
    BRUSSELS_TIME_ZONE,
    build_monthly_peaks,
    build_peak,
    setup_entry,
)


@pytest.mark.usefixtures("mock_engie_client", "frozen_afternoon")
async def test_captar_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the five captar sensors expose the current month's peak."""
    await setup_entry(hass, mock_config_entry)

    power_entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{BAN}_captar_monthly_power_peak"
    )
    assert power_entity_id is not None
    power_state = hass.states.get(power_entity_id)
    assert power_state is not None
    assert power_state.state == "4.2"
    assert power_state.attributes["peak_month"] == "2026-10"
    assert power_state.attributes["peak_is_fallback"] is False

    energy_entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{BAN}_captar_monthly_energy_peak"
    )
    assert energy_entity_id is not None
    assert hass.states.get(energy_entity_id).state == "1.05"

    start_entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{BAN}_captar_monthly_peak_start"
    )
    assert start_entity_id is not None
    start_state = hass.states.get(start_entity_id)
    assert start_state is not None
    assert start_state.state == "2026-10-15T16:00:00+00:00"

    end_entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{BAN}_captar_monthly_peak_end"
    )
    assert end_entity_id is not None
    assert hass.states.get(end_entity_id).state == "2026-10-15T16:15:00+00:00"

    daily_entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{BAN}_captar_daily_power_peak"
    )
    assert daily_entity_id is not None
    daily_entry = entity_registry.async_get(daily_entity_id)
    assert daily_entry is not None
    assert daily_entry.disabled_by == er.RegistryEntryDisabler.INTEGRATION
    assert hass.states.get(daily_entity_id) is None


@pytest.mark.usefixtures(
    "mock_engie_client", "frozen_afternoon", "entity_registry_enabled_by_default"
)
async def test_captar_daily_peak(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the latest daily peak value and its daily_peaks attribute."""
    await setup_entry(hass, mock_config_entry)

    daily_entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{BAN}_captar_daily_power_peak"
    )
    assert daily_entity_id is not None
    daily_state = hass.states.get(daily_entity_id)
    assert daily_state is not None
    assert daily_state.state == "4.2"
    assert daily_state.attributes["daily_peaks"] == [
        {
            "power_kw": 4.2,
            "energy_kwh": 1.05,
            "start": "2026-10-15T18:00:00+02:00",
            "end": "2026-10-15T18:15:00+02:00",
        }
    ]


@pytest.mark.usefixtures("mock_engie_client", "frozen_afternoon")
async def test_captar_fallback_to_previous_month(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the sensors show the previous month's peak until this month has one."""
    september_peak = build_peak(
        datetime(2026, 9, 20, 19, 30, tzinfo=BRUSSELS_TIME_ZONE), power_kw=3.1
    )

    def _peaks(ban: str, year: int, month: int, *, day: int | None = None):
        if (year, month) == (2026, 10):
            return build_monthly_peaks(2026, 10)
        return build_monthly_peaks(2026, 9, peak=september_peak)

    mock_engie_client.return_value.async_get_monthly_peaks.side_effect = _peaks
    await setup_entry(hass, mock_config_entry)

    power_entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{BAN}_captar_monthly_power_peak"
    )
    assert power_entity_id is not None
    power_state = hass.states.get(power_entity_id)
    assert power_state is not None
    assert power_state.state == "3.1"
    assert power_state.attributes["peak_month"] == "2026-09"
    assert power_state.attributes["peak_is_fallback"] is True

    start_entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{BAN}_captar_monthly_peak_start"
    )
    assert start_entity_id is not None
    assert hass.states.get(start_entity_id).state == "2026-09-20T17:30:00+00:00"


@pytest.mark.usefixtures("mock_engie_client", "frozen_afternoon")
async def test_captar_previous_peak_attribute(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the replaced lower peak of the month is exposed as an attribute."""
    current = build_peak(
        datetime(2026, 10, 15, 18, 0, tzinfo=BRUSSELS_TIME_ZONE), power_kw=5.0
    )
    replaced = build_peak(
        datetime(2026, 10, 3, 12, 0, tzinfo=BRUSSELS_TIME_ZONE), power_kw=4.2
    )

    def _peaks(ban: str, year: int, month: int, *, day: int | None = None):
        return build_monthly_peaks(2026, 10, peak=current, previous_peak=replaced)

    mock_engie_client.return_value.async_get_monthly_peaks.side_effect = _peaks
    await setup_entry(hass, mock_config_entry)

    power_entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{BAN}_captar_monthly_power_peak"
    )
    assert power_entity_id is not None
    power_state = hass.states.get(power_entity_id)
    assert power_state is not None
    assert power_state.state == "5.0"
    assert power_state.attributes["previous_peak"] == {
        "power_kw": 4.2,
        "energy_kwh": 1.05,
        "start": "2026-10-03T12:00:00+02:00",
        "end": "2026-10-03T12:15:00+02:00",
    }


@pytest.mark.usefixtures("mock_engie_client", "frozen_afternoon")
async def test_captar_no_peak_yet(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the sensors are unknown when neither month has a peak."""
    mock_engie_client.return_value.async_get_monthly_peaks.side_effect = (
        lambda ban, year, month, *, day=None: build_monthly_peaks(year, month)
    )
    await setup_entry(hass, mock_config_entry)

    power_entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{BAN}_captar_monthly_power_peak"
    )
    assert power_entity_id is not None
    power_state = hass.states.get(power_entity_id)
    assert power_state is not None
    assert power_state.state == "unknown"
    assert power_state.attributes["peak_month"] is None
    assert power_state.attributes["peak_is_fallback"] is False


@pytest.mark.usefixtures("mock_engie_client")
async def test_captar_scheduled_refresh_across_year_rollover(
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

    def _peaks(ban: str, year: int, month: int, *, day: int | None = None):
        if (year, month) == (2026, 11):
            return build_monthly_peaks(2026, 11, peak=november_peak)
        return build_monthly_peaks(year, month)

    peaks_mock = mock_engie_client.return_value.async_get_monthly_peaks
    peaks_mock.side_effect = _peaks
    await setup_entry(hass, mock_config_entry)

    power_entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{BAN}_captar_monthly_power_peak"
    )
    assert power_entity_id is not None
    power_state = hass.states.get(power_entity_id)
    assert power_state is not None
    assert power_state.state == "3.3"
    assert power_state.attributes["peak_month"] == "2026-11"
    assert power_state.attributes["peak_is_fallback"] is True

    freezer.tick(timedelta(days=1, seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

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

    def _peaks_with_january(ban: str, year: int, month: int, *, day: int | None = None):
        if (year, month) == (2027, 1):
            return build_monthly_peaks(
                2027, 1, peak=january_peak, daily_peaks=(january_peak,)
            )
        return _peaks(ban, year, month, day=day)

    peaks_mock.side_effect = _peaks_with_january
    freezer.tick(PEAKS_SCAN_INTERVAL + timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    power_state = hass.states.get(power_entity_id)
    assert power_state is not None
    assert power_state.state == "5.1"
    assert power_state.attributes["peak_month"] == "2027-01"
    assert power_state.attributes["peak_is_fallback"] is False


@pytest.mark.usefixtures("mock_engie_client", "frozen_afternoon")
async def test_captar_auth_error_triggers_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
) -> None:
    """Test an authentication error on the peaks endpoint starts reauthentication."""
    mock_engie_client.return_value.async_get_monthly_peaks.side_effect = (
        EngieBeAuthenticationError("expired")
    )
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is not None
    flows = hass.config_entries.flow.async_progress()
    assert any(flow["context"].get("source") == "reauth" for flow in flows)
