"""The tests for the Sonarr calendar platform."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_time_changed

CALENDAR_ENTITY_ID = "calendar.sonarr"

EPISODE_OVERVIEW = (
    'To compete with fellow "restaurateur," Jimmy Pesto, and his blowout Super Bowl'
    " event, Bob is determined to create a Bob's Burgers commercial to air during the"
    ' "big game." In an effort to outshine Pesto, the Belchers recruit Randy, a'
    " documentarian, to assist with the filmmaking and hire on former pro football star"
    " Connie Frye to be the celebrity endorser."
)


async def test_calendar(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_sonarr: MagicMock,
) -> None:
    """Test for successfully setting up the Sonarr calendar platform."""
    await hass.config.async_update(time_zone="UTC")
    freezer.move_to("2014-01-27T01:30:00+00:00")
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(CALENDAR_ENTITY_ID)
    assert state.state == STATE_ON
    assert state.attributes.get("all_day") is False
    assert state.attributes.get("description") == EPISODE_OVERVIEW
    assert state.attributes.get("end_time") == "2014-01-27 02:00:00"
    assert (
        state.attributes.get("message")
        == "Bob's Burgers - S04E11 - Easy Com-mercial, Easy Go-mercial"
    )
    assert state.attributes.get("start_time") == "2014-01-27 01:30:00"

    freezer.tick(timedelta(minutes=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(CALENDAR_ENTITY_ID)
    assert state.state == STATE_OFF


async def test_calendar_async_get_events(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    init_integration: MockConfigEntry,
    mock_sonarr: MagicMock,
) -> None:
    """Test that async_get_events uses the in-memory cache for repeated calls."""
    freezer.move_to("2014-01-27T00:00:00+00:00")
    coordinator = init_integration.runtime_data.upcoming
    start = datetime(2014, 1, 27, tzinfo=UTC)
    end = start + timedelta(days=1)

    events = await coordinator.async_get_events(start, end)
    assert len(events) == 1
    assert (
        events[0].summary
        == "Bob's Burgers - S04E11 - Easy Com-mercial, Easy Go-mercial"
    )
    call_count = mock_sonarr.async_get_calendar.call_count

    # Second call for the same range is served from cache; no new API call.
    events = await coordinator.async_get_events(start, end)
    assert len(events) == 1
    assert mock_sonarr.async_get_calendar.call_count == call_count

    # A non-overlapping range must return no events even though the cache is warm.
    out_of_range = await coordinator.async_get_events(
        datetime(2014, 1, 28, tzinfo=UTC),
        datetime(2014, 1, 29, tzinfo=UTC),
    )
    assert len(out_of_range) == 0


async def test_calendar_async_get_events_empty_date(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    init_integration: MockConfigEntry,
    mock_sonarr: MagicMock,
) -> None:
    """Test that empty-result dates are cached and not re-fetched."""
    freezer.move_to("2014-01-27T00:00:00+00:00")
    coordinator = init_integration.runtime_data.upcoming
    start = datetime(2014, 1, 27, tzinfo=UTC)
    end = start + timedelta(days=1)

    mock_sonarr.async_get_calendar.return_value = []
    events = await coordinator.async_get_events(start, end)
    assert len(events) == 0
    call_count = mock_sonarr.async_get_calendar.call_count

    # Second call for the same range must not re-fetch the empty date.
    events = await coordinator.async_get_events(start, end)
    assert len(events) == 0
    assert mock_sonarr.async_get_calendar.call_count == call_count


async def test_calendar_no_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_sonarr: MagicMock,
) -> None:
    """Test calendar state with no upcoming episodes."""
    mock_sonarr.async_get_calendar.return_value = []
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(CALENDAR_ENTITY_ID)
    assert state.state == STATE_OFF
