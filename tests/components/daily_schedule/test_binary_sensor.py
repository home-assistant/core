"""The tests for the daily schedule sensor component."""
import datetime
from unittest.mock import patch

import pytest

from homeassistant.components.daily_schedule.const import (
    ATTR_END,
    ATTR_SCHEDULE,
    ATTR_START,
    DOMAIN,
)
from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_time_changed


async def setup_entity(
    hass: HomeAssistant, name: str, schedule: list[dict[str, str]]
) -> None:
    """Create a new entity by adding a config entry."""
    config_entry = MockConfigEntry(
        options={ATTR_SCHEDULE: schedule},
        domain=DOMAIN,
        title=name,
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ["schedule"],
    [
        ([],),
        (
            [
                {
                    ATTR_START: "01:02:03",
                    ATTR_END: "04:05:06",
                },
            ],
        ),
        (
            [
                {
                    ATTR_START: "04:05:06",
                    ATTR_END: "01:02:03",
                },
            ],
        ),
        (
            [
                {
                    ATTR_START: "00:00:00",
                    ATTR_END: "00:00:00",
                },
            ],
        ),
        (
            [
                {
                    ATTR_START: "07:08:09",
                    ATTR_END: "10:11:12",
                },
                {
                    ATTR_START: "01:02:03",
                    ATTR_END: "04:05:06",
                },
            ],
        ),
        (
            [
                {
                    ATTR_START: "10:11:12",
                    ATTR_END: "01:02:03",
                },
                {
                    ATTR_START: "01:02:03",
                    ATTR_END: "04:05:06",
                },
            ],
        ),
    ],
    ids=[
        "empty",
        "single",
        "overnight",
        "entire_day",
        "multiple",
        "adjusted",
    ],
)
async def test_new_sensor(hass, schedule):
    """Test new sensor."""
    entity_id = f"{Platform.BINARY_SENSOR}.my_test"
    await setup_entity(hass, "My Test", schedule)
    schedule.sort(key=lambda period: period[ATTR_START])
    assert hass.states.get(entity_id).attributes[ATTR_SCHEDULE] == schedule


@patch("homeassistant.util.dt.now")
async def test_state(mock_now, hass):
    """Test state attribute."""
    mock_now.return_value = datetime.datetime.fromisoformat("2000-01-01 23:50:00")

    entity_id = f"{Platform.BINARY_SENSOR}.my_test"
    await setup_entity(
        hass,
        "My Test",
        [
            {ATTR_START: "23:50:00", ATTR_END: "23:55:00"},
            {ATTR_START: "00:00:00", ATTR_END: "00:05:00"},
        ],
    )

    assert hass.states.get(entity_id).state == STATE_ON

    state = STATE_OFF
    for _ in range(3):
        mock_now.return_value += datetime.timedelta(minutes=5)
        async_fire_time_changed(hass, mock_now.return_value)
        await hass.async_block_till_done()
        assert hass.states.get(entity_id).state == state
        state = STATE_ON if state == STATE_OFF else STATE_OFF


@pytest.mark.parametrize(
    ["schedule"],
    [
        (
            [
                {
                    ATTR_START: "00:00:00",
                    ATTR_END: "00:00:00",
                },
            ],
        ),
        (
            [
                {
                    ATTR_START: "07:00:00",
                    ATTR_END: "07:00:00",
                },
            ],
        ),
        (
            [
                {
                    ATTR_START: "17:00:00",
                    ATTR_END: "07:00:00",
                },
                {
                    ATTR_START: "07:00:00",
                    ATTR_END: "17:00:00",
                },
            ],
        ),
    ],
    ids=["midnight", "one", "two"],
)
async def test_entire_day(hass, schedule):
    """Test entire day schedule."""
    entity_id = f"{Platform.BINARY_SENSOR}.my_test"
    await setup_entity(hass, "My Test", schedule)
    assert hass.states.get(entity_id).state == STATE_ON


@patch("homeassistant.util.dt.now")
@patch("homeassistant.helpers.event.async_track_point_in_time")
async def test_next_update(async_track_point_in_time, mock_now, hass):
    """Test next update time."""
    mock_now.return_value = datetime.datetime.fromisoformat("2000-01-01")

    in_5_minutes = mock_now.return_value + datetime.timedelta(minutes=5)
    in_10_minutes = mock_now.return_value + datetime.timedelta(minutes=10)
    previous_5_minutes = mock_now.return_value + datetime.timedelta(minutes=-5)
    previous_10_minutes = mock_now.return_value + datetime.timedelta(minutes=-10)

    # No schedule => no updates.
    assert async_track_point_in_time.call_count == 0

    # Inside a time period.
    await setup_entity(
        hass,
        "Test",
        [
            {
                ATTR_START: previous_5_minutes.time().isoformat(),
                ATTR_END: in_5_minutes.time().isoformat(),
            }
        ],
    )
    next_update = async_track_point_in_time.call_args[0][2]
    assert next_update == in_5_minutes

    # After all periods.
    await setup_entity(
        hass,
        "Test",
        [
            {
                ATTR_START: previous_10_minutes.time().isoformat(),
                ATTR_END: previous_5_minutes.time().isoformat(),
            }
        ],
    )
    next_update = async_track_point_in_time.call_args[0][2]
    assert next_update == previous_10_minutes + datetime.timedelta(days=1)

    # Before any period.
    await setup_entity(
        hass,
        "Test",
        [
            {
                ATTR_START: in_5_minutes.time().isoformat(),
                ATTR_END: in_10_minutes.time().isoformat(),
            }
        ],
    )
    next_update = async_track_point_in_time.call_args[0][2]
    assert next_update == in_5_minutes
