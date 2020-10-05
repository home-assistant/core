"""The tests for the schedule class."""
import datetime

import pytest
import voluptuous as vol

from homeassistant.components.daily_schedule.const import ATTR_END, ATTR_START
from homeassistant.components.daily_schedule.schedule import Schedule, TimePeriod


@pytest.mark.parametrize(
    ["start", "end", "time", "result"],
    [
        ("05:00", "10:00", "05:00", True),
        ("05:00", "10:00", "10:00", False),
        ("22:00", "05:00", "23:00", True),
        ("22:00", "05:00", "04:00", True),
        ("22:00", "05:00", "12:00", False),
        ("00:00", "00:00", "00:00", True),
    ],
    ids=[
        "contained",
        "not contained",
        "cross day night",
        "cross day morning",
        "cross day not contained",
        "entire day",
    ],
)
def test_time_period(start: str, end: str, time: str, result: bool):
    """Test for TimePeriod class."""
    period = TimePeriod(start, end)
    assert period.containing(datetime.time.fromisoformat(time)) is result


@pytest.mark.parametrize(
    [
        "param",
    ],
    [
        ({ATTR_START: "05:00:00", ATTR_END: "10:00:00"},),
        ({ATTR_START: "10:00:00", ATTR_END: "05:00:00"},),
        ({ATTR_START: "05:00:00", ATTR_END: "05:00:00"},),
    ],
    ids=[
        "regular",
        "cross day",
        "entire day",
    ],
)
def test_time_period_to_dict(param: dict[str, str]):
    """Test TimePeriod to_dict."""
    assert TimePeriod(param[ATTR_START], param[ATTR_END]).to_dict() == param


@pytest.mark.parametrize(
    ["schedule", "time", "result"],
    [
        ([], "05:00", False),
        ([{ATTR_START: "05:00", ATTR_END: "10:00"}], "05:00", True),
        ([{ATTR_START: "05:00", ATTR_END: "10:00"}], "10:00", False),
        (
            [
                {ATTR_START: "22:00", ATTR_END: "00:00"},
                {ATTR_START: "05:00", ATTR_END: "10:00"},
            ],
            "23:00",
            True,
        ),
    ],
    ids=[
        "empty",
        "contained",
        "not contained",
        "2 periods contained",
    ],
)
def test_schedule_containing(schedule: list[dict[str, str]], time: str, result: bool):
    """Test containing method of Schedule."""
    assert Schedule(schedule).containing(datetime.time.fromisoformat(time)) is result


@pytest.mark.parametrize(
    ["schedule"],
    [
        (
            [
                {
                    ATTR_START: "04:05:05",
                    ATTR_END: "07:08:09",
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
                    ATTR_START: "07:08:09",
                    ATTR_END: "01:02:04",
                },
                {
                    ATTR_START: "01:02:03",
                    ATTR_END: "04:05:06",
                },
            ],
        ),
    ],
    ids=["overlap", "overnight_overlap"],
)
def test_invalid(schedule: list[dict[str, str]]):
    """Test invalid schedule."""
    with pytest.raises(vol.Invalid) as excinfo:
        Schedule(schedule)
    assert "Invalid input schedule" in str(excinfo.value)


@pytest.mark.parametrize(
    ["schedule"],
    [
        (
            [
                {
                    ATTR_START: "01:00:00",
                    ATTR_END: "02:00:00",
                },
            ],
        ),
        (
            [
                {
                    ATTR_START: "03:00:00",
                    ATTR_END: "04:00:00",
                },
                {
                    ATTR_START: "01:00:00",
                    ATTR_END: "02:00:00",
                },
            ],
        ),
    ],
    ids=["one", "two"],
)
def test_to_list(schedule: list[dict[str, str]]) -> None:
    """Test schedule to string list function."""
    str_list = Schedule(schedule).to_list()
    schedule.sort(key=lambda period: period[ATTR_START])
    assert str_list == schedule


@pytest.mark.parametrize(
    ["start_sec_offset", "end_sec_offset", "next_update_sec_offset"],
    [
        (-5, 5, 5),
        (-10, -5, datetime.timedelta(days=1).total_seconds() - 10),
        (5, 10, 5),
    ],
    ids=["inside period", "after all periods", "before all periods"],
)
def test_next_update(
    start_sec_offset: int,
    end_sec_offset: int,
    next_update_sec_offset: int,
) -> None:
    """Test next update logic."""
    now = datetime.datetime.fromisoformat("2000-01-01")
    assert Schedule(
        [
            {
                ATTR_START: (now + datetime.timedelta(seconds=start_sec_offset))
                .time()
                .isoformat(),
                ATTR_END: (now + datetime.timedelta(seconds=end_sec_offset))
                .time()
                .isoformat(),
            }
        ]
    ).next_update(now) == now + datetime.timedelta(seconds=next_update_sec_offset)
