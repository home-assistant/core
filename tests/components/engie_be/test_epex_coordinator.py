"""Test the EPEX coordinator of the ENGIE Belgium integration."""

from datetime import UTC, date, datetime, timedelta
import logging
from unittest.mock import MagicMock

from aioengiebelgium import (
    EngieBeCommunicationError,
    EpexGranularity,
    EpexPayload,
    EpexSlot,
)
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.engie_be.const import DOMAIN
from homeassistant.components.engie_be.coordinator import (
    BRUSSELS_TIME_ZONE,
    EngieBeEpexCoordinator,
    epex_day_available,
    epex_slot_covering,
    epex_slots_for_day,
    epex_trim_slots,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import (
    BAN,
    build_epex_payload,
    build_epex_payload_with_gap,
    build_epex_payload_with_stretched_slot,
    build_epex_payload_without_tomorrow,
    setup_dynamic_entry,
    setup_entry,
)

from tests.common import MockConfigEntry, async_fire_time_changed


def _fetched_days(client: MagicMock) -> list[date]:
    """Return the Brussels day of every EPEX window the client fetched."""
    return [
        call.args[0].astimezone(BRUSSELS_TIME_ZONE).date()
        for call in client.async_get_epex_prices.call_args_list
    ]


def _epex_coordinator(mock_config_entry: MockConfigEntry) -> EngieBeEpexCoordinator:
    """Return the EPEX coordinator of a set up dynamic entry."""
    coordinator = mock_config_entry.runtime_data.epex
    assert coordinator is not None
    return coordinator


def test_epex_trim_slots_only_shortens_oversized_slots() -> None:
    """Test the trim shortens only slots longer than one granularity step."""
    start = datetime(2026, 10, 3, 12, 0, tzinfo=UTC)
    exact = EpexSlot(start=start, end=start + timedelta(hours=1), value_eur_per_kwh=0.1)
    stretched = EpexSlot(
        start=start + timedelta(hours=1),
        end=start + timedelta(hours=3),
        value_eur_per_kwh=0.2,
    )
    short = EpexSlot(
        start=start + timedelta(hours=3),
        end=start + timedelta(hours=3, minutes=30),
        value_eur_per_kwh=0.3,
    )

    trimmed = epex_trim_slots((exact, stretched, short), EpexGranularity.HOURLY)

    assert trimmed == (
        exact,
        EpexSlot(
            start=stretched.start,
            end=stretched.start + timedelta(hours=1),
            value_eur_per_kwh=0.2,
        ),
        short,
    )


async def test_first_refresh_fetches_both_granularities_for_both_days(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    frozen_afternoon: None,
) -> None:
    """Test the first refresh fetches today and tomorrow for both granularities."""
    await setup_dynamic_entry(hass, mock_config_entry, mock_engie_client)

    client = mock_engie_client.return_value
    assert _fetched_days(client) == [
        date(2026, 10, 3),
        date(2026, 10, 3),
        date(2026, 10, 4),
        date(2026, 10, 4),
    ]
    assert [
        call.kwargs["granularity"]
        for call in client.async_get_epex_prices.call_args_list
    ] == [
        EpexGranularity.HOURLY,
        EpexGranularity.QUARTER_HOURLY,
        EpexGranularity.HOURLY,
        EpexGranularity.QUARTER_HOURLY,
    ]


async def test_refresh_makes_no_call_once_both_days_are_covered(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    frozen_afternoon: None,
) -> None:
    """Test a refresh fetches nothing when today and tomorrow are already covered."""
    await setup_dynamic_entry(hass, mock_config_entry, mock_engie_client)

    coordinator = _epex_coordinator(mock_config_entry)
    client = mock_engie_client.return_value
    call_count = client.async_get_epex_prices.call_count

    await coordinator.async_refresh()

    assert client.async_get_epex_prices.call_count == call_count


async def test_tomorrow_not_published_is_tolerated(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    frozen_afternoon: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test an unpublished tomorrow keeps today's data without failing the refresh."""
    caplog.set_level(logging.DEBUG, logger="homeassistant.components.engie_be")
    mock_engie_client.return_value.async_get_epex_prices.side_effect = (
        build_epex_payload_without_tomorrow
    )
    await setup_dynamic_entry(hass, mock_config_entry, mock_engie_client)

    coordinator = _epex_coordinator(mock_config_entry)
    assert coordinator.last_update_success is True
    assert epex_day_available(coordinator.data, date(2026, 10, 4)) is False
    hourly_today = epex_slots_for_day(
        coordinator.data.slots(EpexGranularity.HOURLY), date(2026, 10, 3)
    )
    assert len(hourly_today) == 24
    current = epex_slot_covering(
        coordinator.data.slots(EpexGranularity.HOURLY),
        datetime(2026, 10, 3, 12, 0, tzinfo=UTC),
    )
    assert current is not None
    assert current.value_eur_per_kwh == pytest.approx(0.15)
    assert "Fetching EPEX prices for 2026-10-04 failed" in caplog.text


async def test_today_fetch_failure_does_not_block_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    frozen_afternoon: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a failing EPEX fetch leaves the entry loaded without EPEX data."""
    mock_engie_client.return_value.async_get_epex_prices.side_effect = (
        EngieBeCommunicationError("boom")
    )
    await setup_dynamic_entry(hass, mock_config_entry, mock_engie_client)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert "EPEX prices unavailable at setup" in caplog.text
    assert "connection error" in caplog.text
    coordinator = _epex_coordinator(mock_config_entry)
    assert coordinator.last_update_success is False
    assert coordinator.data is None


async def test_midnight_rollover_fetches_only_the_new_tomorrow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test yesterday's tomorrow slots serve the new day after midnight."""
    freezer.move_to(datetime(2026, 10, 3, 21, 0, tzinfo=BRUSSELS_TIME_ZONE))
    await setup_dynamic_entry(hass, mock_config_entry, mock_engie_client)

    coordinator = _epex_coordinator(mock_config_entry)
    freezer.move_to(datetime(2026, 10, 4, 0, 30, tzinfo=BRUSSELS_TIME_ZONE))
    await coordinator.async_refresh()

    client = mock_engie_client.return_value
    days = _fetched_days(client)
    assert days.count(date(2026, 10, 4)) == 2
    assert days.count(date(2026, 10, 5)) == 2
    assert len(days) == 6
    hourly = coordinator.data.slots(EpexGranularity.HOURLY)
    assert epex_slots_for_day(hourly, date(2026, 10, 3)) == ()
    assert epex_day_available(coordinator.data, date(2026, 10, 4))
    assert epex_day_available(coordinator.data, date(2026, 10, 5))


async def test_fall_back_day_covers_the_repeated_hour(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the 25 hour fall-back day fetches both instances of the repeated hour."""
    freezer.move_to(datetime(2026, 10, 25, 14, 0, tzinfo=BRUSSELS_TIME_ZONE))
    await setup_dynamic_entry(hass, mock_config_entry, mock_engie_client)

    coordinator = _epex_coordinator(mock_config_entry)
    hourly = epex_slots_for_day(
        coordinator.data.slots(EpexGranularity.HOURLY), date(2026, 10, 25)
    )
    assert len(hourly) == 25
    quarter_hourly = epex_slots_for_day(
        coordinator.data.slots(EpexGranularity.QUARTER_HOURLY), date(2026, 10, 25)
    )
    assert len(quarter_hourly) == 100
    first_pass = epex_slot_covering(hourly, datetime(2026, 10, 25, 0, 30, tzinfo=UTC))
    assert first_pass is not None
    assert first_pass.start == datetime(2026, 10, 25, 0, 0, tzinfo=UTC)
    second_pass = epex_slot_covering(hourly, datetime(2026, 10, 25, 1, 30, tzinfo=UTC))
    assert second_pass is not None
    assert second_pass.start == datetime(2026, 10, 25, 1, 0, tzinfo=UTC)
    assert second_pass.end == datetime(2026, 10, 25, 2, 0, tzinfo=UTC)
    assert epex_day_available(coordinator.data, date(2026, 10, 26))


async def test_spring_forward_day_skips_the_missing_hour(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the 23 hour spring-forward day fetches one slot per hour."""
    freezer.move_to(datetime(2026, 3, 29, 14, 0, tzinfo=BRUSSELS_TIME_ZONE))
    await setup_dynamic_entry(hass, mock_config_entry, mock_engie_client)

    coordinator = _epex_coordinator(mock_config_entry)
    hourly = epex_slots_for_day(
        coordinator.data.slots(EpexGranularity.HOURLY), date(2026, 3, 29)
    )
    assert len(hourly) == 23
    quarter_hourly = epex_slots_for_day(
        coordinator.data.slots(EpexGranularity.QUARTER_HOURLY), date(2026, 3, 29)
    )
    assert len(quarter_hourly) == 92
    skipped_hour = epex_slot_covering(hourly, datetime(2026, 3, 29, 1, 30, tzinfo=UTC))
    assert skipped_hour is not None
    assert skipped_hour.start == datetime(2026, 3, 29, 1, 0, tzinfo=UTC)
    assert epex_day_available(coordinator.data, date(2026, 3, 30))


async def test_empty_payload_keeps_entities_unknown(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    frozen_afternoon: None,
) -> None:
    """Test an empty payload leaves the refresh successful and the entities unknown."""

    def _empty_payload(
        start: datetime,
        end: datetime,
        granularity: EpexGranularity = EpexGranularity.HOURLY,
    ) -> EpexPayload:
        """Return an EPEX payload without slots."""
        payload = build_epex_payload(start, end, granularity)
        return EpexPayload(slots=(), slot_duration=payload.slot_duration)

    mock_engie_client.return_value.async_get_epex_prices.side_effect = _empty_payload
    await setup_dynamic_entry(hass, mock_config_entry, mock_engie_client)

    coordinator = _epex_coordinator(mock_config_entry)
    assert coordinator.last_update_success is True
    assert coordinator.data.slots(EpexGranularity.HOURLY) == ()
    current_entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{BAN}_epex_current_hour"
    )
    assert current_entity_id is not None
    current_state = hass.states.get(current_entity_id)
    assert current_state is not None
    assert current_state.state == STATE_UNKNOWN
    binary_entity_id = entity_registry.async_get_entity_id(
        "binary_sensor", DOMAIN, f"{BAN}_epex_tomorrow_available"
    )
    assert binary_entity_id is not None
    binary_state = hass.states.get(binary_entity_id)
    assert binary_state is not None
    assert binary_state.state == STATE_OFF

    client = mock_engie_client.return_value
    call_count = client.async_get_epex_prices.call_count
    await coordinator.async_refresh()
    assert client.async_get_epex_prices.call_count == call_count + 4


async def test_partial_day_is_refetched_and_healed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    frozen_afternoon: None,
) -> None:
    """Test an incomplete day is refetched and healed without duplicate slots."""
    mock_engie_client.return_value.async_get_epex_prices.side_effect = (
        build_epex_payload_with_gap
    )
    await setup_dynamic_entry(hass, mock_config_entry, mock_engie_client)

    coordinator = _epex_coordinator(mock_config_entry)
    client = mock_engie_client.return_value
    hourly_today = epex_slots_for_day(
        coordinator.data.slots(EpexGranularity.HOURLY), date(2026, 10, 3)
    )
    assert len(hourly_today) == 23
    assert epex_day_available(coordinator.data, date(2026, 10, 3)) is False

    call_count = client.async_get_epex_prices.call_count
    client.async_get_epex_prices.side_effect = build_epex_payload
    await coordinator.async_refresh()

    assert client.async_get_epex_prices.call_count == call_count + 1
    assert _fetched_days(client)[-1] == date(2026, 10, 3)
    hourly_today = epex_slots_for_day(
        coordinator.data.slots(EpexGranularity.HOURLY), date(2026, 10, 3)
    )
    assert len(hourly_today) == 24
    assert len({slot.start for slot in hourly_today}) == 24
    assert epex_day_available(coordinator.data, date(2026, 10, 3)) is True


async def test_stretched_slot_is_trimmed_and_healed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    frozen_afternoon: None,
) -> None:
    """Test a stretched slot from a skipped entry is trimmed and healed on refresh."""
    mock_engie_client.return_value.async_get_epex_prices.side_effect = (
        build_epex_payload_with_stretched_slot
    )
    await setup_dynamic_entry(hass, mock_config_entry, mock_engie_client)

    coordinator = _epex_coordinator(mock_config_entry)
    client = mock_engie_client.return_value
    hourly_today = epex_slots_for_day(
        coordinator.data.slots(EpexGranularity.HOURLY), date(2026, 10, 3)
    )
    assert len(hourly_today) == 23
    assert all(slot.end - slot.start == timedelta(hours=1) for slot in hourly_today)
    assert (
        epex_slot_covering(hourly_today, datetime(2026, 10, 3, 13, 30, tzinfo=UTC))
        is None
    )
    quarter_today = epex_slots_for_day(
        coordinator.data.slots(EpexGranularity.QUARTER_HOURLY), date(2026, 10, 3)
    )
    assert len(quarter_today) == 95
    assert all(slot.end - slot.start == timedelta(minutes=15) for slot in quarter_today)
    assert epex_day_available(coordinator.data, date(2026, 10, 3)) is False

    call_count = client.async_get_epex_prices.call_count
    client.async_get_epex_prices.side_effect = build_epex_payload
    await coordinator.async_refresh()

    assert client.async_get_epex_prices.call_count == call_count + 2
    assert _fetched_days(client)[-2:] == [date(2026, 10, 3), date(2026, 10, 3)]
    hourly_today = epex_slots_for_day(
        coordinator.data.slots(EpexGranularity.HOURLY), date(2026, 10, 3)
    )
    assert len(hourly_today) == 24
    assert epex_day_available(coordinator.data, date(2026, 10, 3)) is True


async def test_listener_stops_on_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    frozen_afternoon: None,
) -> None:
    """Test the quarter-hour listener is cancelled when the entry unloads."""
    await setup_dynamic_entry(hass, mock_config_entry, mock_engie_client)

    coordinator = _epex_coordinator(mock_config_entry)
    assert coordinator.listener_unsub is not None
    binary_entity_id = entity_registry.async_get_entity_id(
        "binary_sensor", DOMAIN, f"{BAN}_epex_tomorrow_available"
    )
    assert binary_entity_id is not None

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert coordinator.listener_unsub is None

    freezer.move_to(datetime(2026, 10, 3, 14, 15, tzinfo=BRUSSELS_TIME_ZONE))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert coordinator.listener_unsub is None


async def test_no_epex_coordinator_without_dynamic_household(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    frozen_afternoon: None,
) -> None:
    """Test a fixed-tariff entry sets up no EPEX coordinator at all."""
    await setup_entry(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data.epex is None
    assert (
        entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{BAN}_epex_current_hour"
        )
        is None
    )
