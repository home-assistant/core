"""Test the Skylight calendar platform."""

from datetime import UTC, datetime, timedelta
import itertools
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from skylight_api import SkylightAPI, SkylightAPIError, SkylightAuthError

from homeassistant.components.calendar import (
    DOMAIN as CALENDAR_DOMAIN,
    SERVICE_GET_EVENTS,
    CalendarEntityFeature,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import EVENT_END, EVENT_START

from tests.common import MockConfigEntry, async_fire_time_changed

ALL_DAY_RAW = {
    "data": [
        {
            "id": "event-all-day-multi",
            "attributes": {
                "summary": "Trip",
                # Skylight all-day: bare dates, inclusive last day.
                "starts_at": "2030-10-10",
                "ends_at": "2030-10-12",
            },
        }
    ]
}


@pytest.mark.usefixtures("mock_coordinator_data")
async def test_calendar_entity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the calendar entity is set up."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("calendar.home_frame_calendar")
    assert state is not None
    assert state.state == "off"


@pytest.mark.usefixtures("mock_coordinator_data")
async def test_calendar_get_events(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test calendar.get_events returns the coordinator's events."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.services.async_call(
        CALENDAR_DOMAIN,
        SERVICE_GET_EVENTS,
        {
            "entity_id": "calendar.home_frame_calendar",
            "start_date_time": EVENT_START - timedelta(days=1),
            "end_date_time": EVENT_END + timedelta(days=1),
        },
        blocking=True,
        return_response=True,
    )
    events = result["calendar.home_frame_calendar"]["events"]
    assert events == [
        {
            "start": EVENT_START.isoformat(),
            "end": EVENT_END.isoformat(),
            "summary": "Family dinner",
            "description": "At grandma's",
        }
    ]


@pytest.mark.usefixtures("mock_coordinator_data")
async def test_calendar_is_read_only(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the entity is read-only: no write features are advertised."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("calendar.home_frame_calendar")
    features = int(state.attributes.get("supported_features") or 0)
    assert features & CalendarEntityFeature.CREATE_EVENT == 0
    assert features & CalendarEntityFeature.UPDATE_EVENT == 0
    assert features & CalendarEntityFeature.DELETE_EVENT == 0


async def test_all_day_event_inclusive_end_and_range_query(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test all-day events: exclusive end keeps the last day, date/datetime mix works."""
    freezer.move_to(datetime(2030, 10, 10, 12, 0, tzinfo=UTC))
    with patch(
        "skylight_api.SkylightAPI.get_calendar_events",
        return_value=ALL_DAY_RAW,
    ):
        mock_config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.services.async_call(
        CALENDAR_DOMAIN,
        SERVICE_GET_EVENTS,
        {
            "entity_id": "calendar.home_frame_calendar",
            "start_date_time": datetime(2030, 10, 12, 0, 0, tzinfo=UTC),
            "end_date_time": datetime(2030, 10, 12, 23, 59, tzinfo=UTC),
        },
        blocking=True,
        return_response=True,
    )
    events = result["calendar.home_frame_calendar"]["events"]
    # The inclusive final day (Oct 12) must be covered by the exclusive end.
    assert len(events) == 1
    assert events[0]["start"] == "2030-10-10"
    assert events[0]["end"] == "2030-10-13"

    state = hass.states.get("calendar.home_frame_calendar")
    assert state is not None


async def test_get_events_outside_window_fetches_live(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a range query past the rolling window fetches events live."""
    freezer.move_to(datetime(2030, 6, 1, 12, 0, tzinfo=UTC))
    in_window = {
        "data": [
            {
                "id": "event-1",
                "attributes": {
                    "summary": "In window",
                    "starts_at": "2030-06-02T09:00:00+00:00",
                    "ends_at": "2030-06-02T10:00:00+00:00",
                },
            }
        ]
    }
    far_future = {
        "data": [
            {
                "id": "event-far",
                "attributes": {
                    "summary": "Far future",
                    "starts_at": "2031-01-05T09:00:00+00:00",
                    "ends_at": "2031-01-05T10:00:00+00:00",
                },
            },
            {
                "id": "event-1",
                "attributes": {
                    "summary": "In window",
                    "starts_at": "2030-06-02T09:00:00+00:00",
                    "ends_at": "2030-06-02T10:00:00+00:00",
                },
            },
        ]
    }

    async def _get_events(_frame_id, *, date_min, date_max):
        if date_max >= "2031-01-01":
            return far_future
        return in_window

    with patch("skylight_api.SkylightAPI.get_calendar_events", side_effect=_get_events):
        mock_config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.services.async_call(
            CALENDAR_DOMAIN,
            SERVICE_GET_EVENTS,
            {
                "entity_id": "calendar.home_frame_calendar",
                "start_date_time": datetime(2031, 1, 1, tzinfo=UTC),
                "end_date_time": datetime(2031, 1, 31, tzinfo=UTC),
            },
            blocking=True,
            return_response=True,
        )
    events = result["calendar.home_frame_calendar"]["events"]
    assert [event["summary"] for event in events] == ["Far future"]


async def test_get_events_outside_window_degrades_to_cache_on_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a failed live fetch for an out-of-window range falls back to cache."""
    freezer.move_to(datetime(2030, 6, 1, 12, 0, tzinfo=UTC))
    in_window = {
        "data": [
            {
                "id": "event-1",
                "attributes": {
                    "summary": "In window",
                    "starts_at": "2030-06-02T09:00:00+00:00",
                    "ends_at": "2030-06-02T10:00:00+00:00",
                },
            }
        ]
    }

    async def _get_events(_frame_id, *, date_min, date_max):
        if date_max >= "2031-01-01":
            raise SkylightAPIError("endpoint down")
        return in_window

    with patch("skylight_api.SkylightAPI.get_calendar_events", side_effect=_get_events):
        mock_config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.services.async_call(
            CALENDAR_DOMAIN,
            SERVICE_GET_EVENTS,
            {
                "entity_id": "calendar.home_frame_calendar",
                "start_date_time": datetime(2031, 1, 1, tzinfo=UTC),
                "end_date_time": datetime(2031, 1, 31, tzinfo=UTC),
            },
            blocking=True,
            return_response=True,
        )
    assert result["calendar.home_frame_calendar"]["events"] == []


async def test_coordinator_setup_retry_then_recovery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a failing API call retries with backoff and then recovers."""
    raw_events = {
        "data": [
            {
                "id": "event-1",
                "attributes": {
                    "summary": "Family dinner",
                    "starts_at": "2026-10-10T09:00:00+00:00",
                    "ends_at": "2026-10-10T10:00:00+00:00",
                },
            }
        ]
    }
    with patch(
        "skylight_api.SkylightAPI.get_calendar_events",
        side_effect=itertools.chain(
            [SkylightAPIError("boom")], itertools.repeat(raw_events)
        ),
    ):
        mock_config_entry.add_to_hass(hass)
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY

        for _ in range(20):
            if mock_config_entry.state is ConfigEntryState.LOADED:
                break
            freezer.tick(timedelta(minutes=1))
            async_fire_time_changed(hass)
            await hass.async_block_till_done()
        await hass.async_block_till_done()
        assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_coordinator_skips_malformed_events(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test events with missing or unparsable dates are skipped, not fatal."""
    raw_events = {
        "data": [
            {"id": "e-missing", "attributes": {"summary": "no dates"}},
            {
                "id": "e-bad",
                "attributes": {
                    "summary": "bad dates",
                    "starts_at": "not-a-date",
                    "ends_at": "2030-10-12",
                },
            },
            {
                "id": "e-good",
                "attributes": {
                    "summary": "Fine",
                    "starts_at": "2030-10-10T09:00:00+00:00",
                    "ends_at": "2030-10-10T10:00:00+00:00",
                },
            },
            {
                "id": "e-mixed",
                "attributes": {
                    "summary": "Date start, datetime end",
                    "starts_at": "2030-10-10",
                    "ends_at": "2030-10-10T10:00:00+00:00",
                },
            },
            {"id": "no-attributes"},
        ]
    }
    # The service call stays inside the patch scope: the requested 2030
    # range is outside the rolling poll window, so the coordinator live
    # fetches via the same API method.
    with patch(
        "skylight_api.SkylightAPI.get_calendar_events",
        return_value=raw_events,
    ):
        mock_config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.services.async_call(
            CALENDAR_DOMAIN,
            SERVICE_GET_EVENTS,
            {
                "entity_id": "calendar.home_frame_calendar",
                "start_date_time": datetime(2030, 10, 9, tzinfo=UTC),
                "end_date_time": datetime(2030, 10, 13, tzinfo=UTC),
            },
            blocking=True,
            return_response=True,
        )
    events = result["calendar.home_frame_calendar"]["events"]
    assert [event["summary"] for event in events] == [
        "Fine",
        "Date start, datetime end",
    ]


async def test_coordinator_auth_error_triggers_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a SkylightAuthError on poll starts the reauth flow."""
    with patch(
        "skylight_api.SkylightAPI.get_calendar_events",
        side_effect=SkylightAuthError("expired"),
    ):
        mock_config_entry.add_to_hass(hass)
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_token_rotation_persists_new_tokens(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the client's refresh cascade persists rotated tokens to the entry."""
    captured: dict[str, Any] = {}

    real_init = SkylightAPI.__init__

    def _capture_init(self: SkylightAPI, *args: Any, **kwargs: Any) -> None:
        real_init(self, *args, **kwargs)
        captured.update(kwargs)

    with (
        patch(
            "skylight_api.SkylightAPI.get_calendar_events",
            return_value={"data": []},
        ),
        patch.object(SkylightAPI, "__init__", _capture_init),
    ):
        mock_config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert entry is not None

    # Invoke the token_update_cb the integration registered at setup, exactly
    # as the client's refresh cascade would, instead of reaching into the
    # client's private session/refresh internals.
    callback = captured["token_update_cb"]
    assert callback is not None
    await callback("rotated-access", "rotated-refresh", "mock-fingerprint")
    await hass.async_block_till_done()

    token = mock_config_entry.data["token"]
    assert token["access_token"] == "rotated-access"
    assert token["refresh_token"] == "rotated-refresh"
    assert token["device_fingerprint"] == "mock-fingerprint"
