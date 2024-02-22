"""Test Home Assistant date util methods."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

import homeassistant.util.dt as dt_util

DEFAULT_TIME_ZONE = dt_util.DEFAULT_TIME_ZONE
TEST_TIME_ZONE = "America/Los_Angeles"


@pytest.fixture(autouse=True)
def teardown():
    """Stop everything that was started."""
    yield

    dt_util.set_default_time_zone(DEFAULT_TIME_ZONE)


def test_get_time_zone_retrieves_valid_time_zone() -> None:
    """Test getting a time zone."""
    assert dt_util.get_time_zone(TEST_TIME_ZONE) is not None


def test_get_time_zone_returns_none_for_garbage_time_zone() -> None:
    """Test getting a non existing time zone."""
    assert dt_util.get_time_zone("Non existing time zone") is None


def test_set_default_time_zone() -> None:
    """Test setting default time zone."""
    time_zone = dt_util.get_time_zone(TEST_TIME_ZONE)

    dt_util.set_default_time_zone(time_zone)

    assert dt_util.now().tzinfo is time_zone


def test_utcnow() -> None:
    """Test the UTC now method."""
    assert abs(
        dt_util.utcnow().replace(tzinfo=None) - datetime.now(UTC).replace(tzinfo=None)
    ) < timedelta(seconds=1)


def test_now() -> None:
    """Test the now method."""
    dt_util.set_default_time_zone(dt_util.get_time_zone(TEST_TIME_ZONE))

    assert abs(
        dt_util.as_utc(dt_util.now()).replace(tzinfo=None)
        - datetime.now(UTC).replace(tzinfo=None)
    ) < timedelta(seconds=1)


def test_as_utc_with_naive_object() -> None:
    """Test the now method."""
    utcnow = datetime.now(UTC).replace(tzinfo=None)

    assert utcnow == dt_util.as_utc(utcnow).replace(tzinfo=None)


def test_as_utc_with_utc_object() -> None:
    """Test UTC time with UTC object."""
    utcnow = dt_util.utcnow()

    assert utcnow == dt_util.as_utc(utcnow)


def test_as_utc_with_local_object() -> None:
    """Test the UTC time with local object."""
    dt_util.set_default_time_zone(dt_util.get_time_zone(TEST_TIME_ZONE))
    localnow = dt_util.now()
    utcnow = dt_util.as_utc(localnow)

    assert localnow == utcnow
    assert localnow.tzinfo != utcnow.tzinfo


def test_as_local_with_naive_object() -> None:
    """Test local time with native object."""
    now = dt_util.now()
    assert abs(
        now - dt_util.as_local(datetime.now(UTC).replace(tzinfo=None))
    ) < timedelta(seconds=1)


def test_as_local_with_local_object() -> None:
    """Test local with local object."""
    now = dt_util.now()
    assert now == now


def test_as_local_with_utc_object() -> None:
    """Test local time with UTC object."""
    dt_util.set_default_time_zone(dt_util.get_time_zone(TEST_TIME_ZONE))

    utcnow = dt_util.utcnow()
    localnow = dt_util.as_local(utcnow)

    assert localnow == utcnow
    assert localnow.tzinfo != utcnow.tzinfo


def test_utc_from_timestamp() -> None:
    """Test utc_from_timestamp method."""
    assert datetime(1986, 7, 9, tzinfo=dt_util.UTC) == dt_util.utc_from_timestamp(
        521251200
    )


def test_timestamp_to_utc() -> None:
    """Test we can convert a utc datetime to a timestamp."""
    utc_now = dt_util.utcnow()
    assert dt_util.utc_to_timestamp(utc_now) == utc_now.timestamp()


def test_as_timestamp() -> None:
    """Test as_timestamp method."""
    ts = 1462401234
    utc_dt = dt_util.utc_from_timestamp(ts)
    assert ts == dt_util.as_timestamp(utc_dt)
    utc_iso = utc_dt.isoformat()
    assert ts == dt_util.as_timestamp(utc_iso)

    # confirm the ability to handle a string passed in
    delta = dt_util.as_timestamp("2016-01-01 12:12:12")
    delta -= dt_util.as_timestamp("2016-01-01 12:12:11")
    assert delta == 1


def test_parse_datetime_converts_correctly() -> None:
    """Test parse_datetime converts strings."""
    assert datetime(1986, 7, 9, 12, 0, 0, tzinfo=dt_util.UTC) == dt_util.parse_datetime(
        "1986-07-09T12:00:00Z"
    )

    utcnow = dt_util.utcnow()

    assert utcnow == dt_util.parse_datetime(utcnow.isoformat())


def test_parse_datetime_returns_none_for_incorrect_format() -> None:
    """Test parse_datetime returns None if incorrect format."""
    assert dt_util.parse_datetime("not a datetime string") is None


def test_parse_datetime_raises_for_incorrect_format() -> None:
    """Test parse_datetime raises ValueError if raise_on_error is set with an incorrect format."""
    with pytest.raises(ValueError):
        dt_util.parse_datetime("not a datetime string", raise_on_error=True)


@pytest.mark.parametrize(
    ("duration_string", "expected_result"),
    [
        ("PT10M", timedelta(minutes=10)),
        ("PT0S", timedelta(0)),
        ("P10DT11H11M01S", timedelta(days=10, hours=11, minutes=11, seconds=1)),
        (
            "4 1:20:30.111111",
            timedelta(days=4, hours=1, minutes=20, seconds=30, microseconds=111111),
        ),
        ("4 1:2:30", timedelta(days=4, hours=1, minutes=2, seconds=30)),
        ("3 days 04:05:06", timedelta(days=3, hours=4, minutes=5, seconds=6)),
        ("P1YT10M", None),
        ("P1MT10M", None),
        ("1MT10M", None),
        ("P1MT100M", None),
        ("P1234", None),
    ],
)
def test_parse_duration(
    duration_string: str, expected_result: timedelta | None
) -> None:
    """Test that parse_duration returns the expected result."""
    assert dt_util.parse_duration(duration_string) == expected_result


def test_get_age() -> None:
    """Test get_age."""
    diff = dt_util.now() - timedelta(seconds=0)
    assert dt_util.get_age(diff) == "0 seconds"

    diff = dt_util.now() - timedelta(seconds=1)
    assert dt_util.get_age(diff) == "1 second"

    diff = dt_util.now() - timedelta(seconds=30)
    assert dt_util.get_age(diff) == "30 seconds"

    diff = dt_util.now() - timedelta(minutes=5)
    assert dt_util.get_age(diff) == "5 minutes"

    diff = dt_util.now() - timedelta(minutes=1)
    assert dt_util.get_age(diff) == "1 minute"

    diff = dt_util.now() - timedelta(minutes=300)
    assert dt_util.get_age(diff) == "5 hours"

    diff = dt_util.now() - timedelta(minutes=320)
    assert dt_util.get_age(diff) == "5 hours"

    diff = dt_util.now() - timedelta(minutes=1.6 * 60 * 24)
    assert dt_util.get_age(diff) == "2 days"

    diff = dt_util.now() - timedelta(minutes=2 * 60 * 24)
    assert dt_util.get_age(diff) == "2 days"

    diff = dt_util.now() - timedelta(minutes=32 * 60 * 24)
    assert dt_util.get_age(diff) == "1 month"

    diff = dt_util.now() - timedelta(minutes=365 * 60 * 24)
    assert dt_util.get_age(diff) == "1 year"


def test_parse_time_expression() -> None:
    """Test parse_time_expression."""
    assert list(range(60)) == dt_util.parse_time_expression("*", 0, 59)
    assert list(range(60)) == dt_util.parse_time_expression(None, 0, 59)

    assert list(range(0, 60, 5)) == dt_util.parse_time_expression("/5", 0, 59)

    assert [1, 2, 3] == dt_util.parse_time_expression([2, 1, 3], 0, 59)

    assert list(range(24)) == dt_util.parse_time_expression("*", 0, 23)

    assert [42] == dt_util.parse_time_expression(42, 0, 59)
    assert [42] == dt_util.parse_time_expression("42", 0, 59)

    with pytest.raises(ValueError):
        dt_util.parse_time_expression(61, 0, 60)


def test_find_next_time_expression_time_basic() -> None:
    """Test basic stuff for find_next_time_expression_time."""

    def find(dt, hour, minute, second):
        """Call test_find_next_time_expression_time."""
        seconds = dt_util.parse_time_expression(second, 0, 59)
        minutes = dt_util.parse_time_expression(minute, 0, 59)
        hours = dt_util.parse_time_expression(hour, 0, 23)

        return dt_util.find_next_time_expression_time(dt, seconds, minutes, hours)

    assert datetime(2018, 10, 7, 10, 30, 0) == find(
        datetime(2018, 10, 7, 10, 20, 0), "*", "/30", 0
    )

    assert datetime(2018, 10, 7, 10, 30, 0) == find(
        datetime(2018, 10, 7, 10, 30, 0), "*", "/30", 0
    )

    assert datetime(2018, 10, 7, 12, 0, 30) == find(
        datetime(2018, 10, 7, 10, 30, 0), "/3", "/30", [30, 45]
    )

    assert datetime(2018, 10, 8, 5, 0, 0) == find(
        datetime(2018, 10, 7, 10, 30, 0), 5, 0, 0
    )

    assert find(datetime(2018, 10, 7, 10, 30, 0, 999999), "*", "/30", 0) == datetime(
        2018, 10, 7, 10, 30, 0
    )


def test_find_next_time_expression_time_dst() -> None:
    """Test daylight saving time for find_next_time_expression_time."""
    tz = dt_util.get_time_zone("Europe/Vienna")
    dt_util.set_default_time_zone(tz)

    def find(dt, hour, minute, second) -> datetime:
        """Call test_find_next_time_expression_time."""
        seconds = dt_util.parse_time_expression(second, 0, 59)
        minutes = dt_util.parse_time_expression(minute, 0, 59)
        hours = dt_util.parse_time_expression(hour, 0, 23)

        local = dt_util.find_next_time_expression_time(dt, seconds, minutes, hours)
        return dt_util.as_utc(local)

    # Entering DST, clocks are rolled forward
    assert dt_util.as_utc(datetime(2018, 3, 26, 2, 30, 0, tzinfo=tz)) == find(
        datetime(2018, 3, 25, 1, 50, 0, tzinfo=tz), 2, 30, 0
    )

    assert dt_util.as_utc(datetime(2018, 3, 26, 2, 30, 0, tzinfo=tz)) == find(
        datetime(2018, 3, 25, 3, 50, 0, tzinfo=tz), 2, 30, 0
    )

    assert dt_util.as_utc(datetime(2018, 3, 26, 2, 30, 0, tzinfo=tz)) == find(
        datetime(2018, 3, 26, 1, 50, 0, tzinfo=tz), 2, 30, 0
    )

    # Leaving DST, clocks are rolled back
    assert dt_util.as_utc(datetime(2018, 10, 28, 2, 30, 0, tzinfo=tz, fold=0)) == find(
        datetime(2018, 10, 28, 2, 5, 0, tzinfo=tz, fold=0), 2, 30, 0
    )

    assert dt_util.as_utc(datetime(2018, 10, 28, 2, 30, 0, tzinfo=tz, fold=0)) == find(
        datetime(2018, 10, 28, 2, 5, 0, tzinfo=tz), 2, 30, 0
    )

    assert dt_util.as_utc(datetime(2018, 10, 28, 2, 30, 0, tzinfo=tz, fold=1)) == find(
        datetime(2018, 10, 28, 2, 55, 0, tzinfo=tz), 2, 30, 0
    )

    assert dt_util.as_utc(datetime(2018, 10, 28, 2, 30, 0, tzinfo=tz, fold=1)) == find(
        datetime(2018, 10, 28, 2, 55, 0, tzinfo=tz, fold=0), 2, 30, 0
    )

    assert dt_util.as_utc(datetime(2018, 10, 28, 4, 30, 0, tzinfo=tz, fold=0)) == find(
        datetime(2018, 10, 28, 2, 55, 0, tzinfo=tz, fold=1), 4, 30, 0
    )

    assert dt_util.as_utc(datetime(2018, 10, 28, 2, 30, 0, tzinfo=tz, fold=1)) == find(
        datetime(2018, 10, 28, 2, 5, 0, tzinfo=tz, fold=1), 2, 30, 0
    )

    assert dt_util.as_utc(datetime(2018, 10, 28, 2, 30, 0, tzinfo=tz, fold=1)) == find(
        datetime(2018, 10, 28, 2, 55, 0, tzinfo=tz, fold=0), 2, 30, 0
    )


# DST begins on 2021.03.28 2:00, clocks were turned forward 1h; 2:00-3:00 time does not exist
@pytest.mark.parametrize(
    ("now_dt", "expected_dt"),
    [
        # 00:00 -> 2:30
        (
            datetime(2021, 3, 28, 0, 0, 0),
            datetime(2021, 3, 29, 2, 30, 0),
        ),
    ],
)
def test_find_next_time_expression_entering_dst(now_dt, expected_dt) -> None:
    """Test entering daylight saving time for find_next_time_expression_time."""
    tz = dt_util.get_time_zone("Europe/Vienna")
    dt_util.set_default_time_zone(tz)
    # match on 02:30:00 every day
    pattern_seconds = dt_util.parse_time_expression(0, 0, 59)
    pattern_minutes = dt_util.parse_time_expression(30, 0, 59)
    pattern_hours = dt_util.parse_time_expression(2, 0, 59)

    now_dt = now_dt.replace(tzinfo=tz)
    expected_dt = expected_dt.replace(tzinfo=tz)

    res_dt = dt_util.find_next_time_expression_time(
        now_dt, pattern_seconds, pattern_minutes, pattern_hours
    )
    assert dt_util.as_utc(res_dt) == dt_util.as_utc(expected_dt)


# DST ends on 2021.10.31 2:00, clocks were turned backward 1h; 2:00-3:00 time is ambiguous
@pytest.mark.parametrize(
    ("now_dt", "expected_dt"),
    [
        # 00:00 -> 2:30
        (
            datetime(2021, 10, 31, 0, 0, 0),
            datetime(2021, 10, 31, 2, 30, 0, fold=0),
        ),
        # 02:00(0) -> 2:30(0)
        (
            datetime(2021, 10, 31, 2, 0, 0, fold=0),
            datetime(2021, 10, 31, 2, 30, 0, fold=0),
        ),
        # 02:15(0) -> 2:30(0)
        (
            datetime(2021, 10, 31, 2, 15, 0, fold=0),
            datetime(2021, 10, 31, 2, 30, 0, fold=0),
        ),
        # 02:30:00(0) -> 2:30(1)
        (
            datetime(2021, 10, 31, 2, 30, 0, fold=0),
            datetime(2021, 10, 31, 2, 30, 0, fold=0),
        ),
        # 02:30:01(0) -> 2:30(1)
        (
            datetime(2021, 10, 31, 2, 30, 1, fold=0),
            datetime(2021, 10, 31, 2, 30, 0, fold=1),
        ),
        # 02:45(0) -> 2:30(1)
        (
            datetime(2021, 10, 31, 2, 45, 0, fold=0),
            datetime(2021, 10, 31, 2, 30, 0, fold=1),
        ),
        # 02:00(1) -> 2:30(1)
        (
            datetime(2021, 10, 31, 2, 0, 0, fold=1),
            datetime(2021, 10, 31, 2, 30, 0, fold=1),
        ),
        # 02:15(1) -> 2:30(1)
        (
            datetime(2021, 10, 31, 2, 15, 0, fold=1),
            datetime(2021, 10, 31, 2, 30, 0, fold=1),
        ),
        # 02:30:00(1) -> 2:30(1)
        (
            datetime(2021, 10, 31, 2, 30, 0, fold=1),
            datetime(2021, 10, 31, 2, 30, 0, fold=1),
        ),
        # 02:30:01(1) -> 2:30 next day
        (
            datetime(2021, 10, 31, 2, 30, 1, fold=1),
            datetime(2021, 11, 1, 2, 30, 0),
        ),
        # 02:45(1) -> 2:30 next day
        (
            datetime(2021, 10, 31, 2, 45, 0, fold=1),
            datetime(2021, 11, 1, 2, 30, 0),
        ),
        # 08:00(1) -> 2:30 next day
        (
            datetime(2021, 10, 31, 8, 0, 1),
            datetime(2021, 11, 1, 2, 30, 0),
        ),
    ],
)
def test_find_next_time_expression_exiting_dst(now_dt, expected_dt) -> None:
    """Test exiting daylight saving time for find_next_time_expression_time."""
    tz = dt_util.get_time_zone("Europe/Vienna")
    dt_util.set_default_time_zone(tz)
    # match on 02:30:00 every day
    pattern_seconds = dt_util.parse_time_expression(0, 0, 59)
    pattern_minutes = dt_util.parse_time_expression(30, 0, 59)
    pattern_hours = dt_util.parse_time_expression(2, 0, 59)

    now_dt = now_dt.replace(tzinfo=tz)
    expected_dt = expected_dt.replace(tzinfo=tz)

    res_dt = dt_util.find_next_time_expression_time(
        now_dt, pattern_seconds, pattern_minutes, pattern_hours
    )
    assert dt_util.as_utc(res_dt) == dt_util.as_utc(expected_dt)


def test_find_next_time_expression_time_dst_chicago() -> None:
    """Test daylight saving time for find_next_time_expression_time."""
    tz = dt_util.get_time_zone("America/Chicago")
    dt_util.set_default_time_zone(tz)

    def find(dt, hour, minute, second) -> datetime:
        """Call test_find_next_time_expression_time."""
        seconds = dt_util.parse_time_expression(second, 0, 59)
        minutes = dt_util.parse_time_expression(minute, 0, 59)
        hours = dt_util.parse_time_expression(hour, 0, 23)

        local = dt_util.find_next_time_expression_time(dt, seconds, minutes, hours)
        return dt_util.as_utc(local)

    # Entering DST, clocks are rolled forward
    assert dt_util.as_utc(datetime(2021, 3, 15, 2, 30, 0, tzinfo=tz)) == find(
        datetime(2021, 3, 14, 1, 50, 0, tzinfo=tz), 2, 30, 0
    )

    assert dt_util.as_utc(datetime(2021, 3, 15, 2, 30, 0, tzinfo=tz)) == find(
        datetime(2021, 3, 14, 3, 50, 0, tzinfo=tz), 2, 30, 0
    )

    assert dt_util.as_utc(datetime(2021, 3, 15, 2, 30, 0, tzinfo=tz)) == find(
        datetime(2021, 3, 14, 1, 50, 0, tzinfo=tz), 2, 30, 0
    )

    assert dt_util.as_utc(datetime(2021, 3, 14, 3, 30, 0, tzinfo=tz)) == find(
        datetime(2021, 3, 14, 1, 50, 0, tzinfo=tz), 3, 30, 0
    )

    # Leaving DST, clocks are rolled back
    assert dt_util.as_utc(datetime(2021, 11, 7, 2, 30, 0, tzinfo=tz, fold=0)) == find(
        datetime(2021, 11, 7, 2, 5, 0, tzinfo=tz, fold=0), 2, 30, 0
    )

    assert dt_util.as_utc(datetime(2021, 11, 7, 2, 30, 0, tzinfo=tz)) == find(
        datetime(2021, 11, 7, 2, 5, 0, tzinfo=tz), 2, 30, 0
    )

    assert dt_util.as_utc(datetime(2021, 11, 7, 2, 30, 0, tzinfo=tz, fold=0)) == find(
        datetime(2021, 11, 7, 2, 5, 0, tzinfo=tz), 2, 30, 0
    )

    assert dt_util.as_utc(datetime(2021, 11, 7, 2, 30, 0, tzinfo=tz, fold=1)) == find(
        datetime(2021, 11, 7, 2, 10, 0, tzinfo=tz), 2, 30, 0
    )

    assert dt_util.as_utc(datetime(2021, 11, 7, 2, 30, 0, tzinfo=tz, fold=1)) == find(
        datetime(2021, 11, 7, 2, 30, 0, tzinfo=tz, fold=0), 2, 30, 0
    )

    assert dt_util.as_utc(datetime(2021, 11, 8, 2, 30, 0, tzinfo=tz, fold=1)) == find(
        datetime(2021, 11, 7, 2, 55, 0, tzinfo=tz, fold=0), 2, 30, 0
    )

    assert dt_util.as_utc(datetime(2021, 11, 7, 4, 30, 0, tzinfo=tz, fold=0)) == find(
        datetime(2021, 11, 7, 2, 55, 0, tzinfo=tz, fold=1), 4, 30, 0
    )

    assert dt_util.as_utc(datetime(2021, 11, 7, 2, 30, 0, tzinfo=tz, fold=1)) == find(
        datetime(2021, 11, 7, 2, 5, 0, tzinfo=tz, fold=1), 2, 30, 0
    )

    assert dt_util.as_utc(datetime(2021, 11, 8, 2, 30, 0, tzinfo=tz)) == find(
        datetime(2021, 11, 7, 2, 55, 0, tzinfo=tz, fold=0), 2, 30, 0
    )


def _get_matches(hours, minutes, seconds):
    matching_hours = dt_util.parse_time_expression(hours, 0, 23)
    matching_minutes = dt_util.parse_time_expression(minutes, 0, 59)
    matching_seconds = dt_util.parse_time_expression(seconds, 0, 59)
    return matching_hours, matching_minutes, matching_seconds


def test_find_next_time_expression_day_before_dst_change_the_same_time() -> None:
    """Test the day before DST to establish behavior without DST."""
    tz = dt_util.get_time_zone("America/Chicago")
    dt_util.set_default_time_zone(tz)

    # Not in DST yet
    hour_minute_second = (12, 30, 1)
    test_time = datetime(2021, 10, 7, *hour_minute_second, tzinfo=tz, fold=0)
    matching_hours, matching_minutes, matching_seconds = _get_matches(
        *hour_minute_second
    )
    next_time = dt_util.find_next_time_expression_time(
        test_time, matching_seconds, matching_minutes, matching_hours
    )
    assert next_time == datetime(2021, 10, 7, *hour_minute_second, tzinfo=tz, fold=0)
    assert next_time.fold == 0
    assert dt_util.as_utc(next_time) == datetime(
        2021, 10, 7, 17, 30, 1, tzinfo=dt_util.UTC
    )


def test_find_next_time_expression_time_leave_dst_chicago_before_the_fold_30_s() -> (
    None
):
    """Test leaving daylight saving time for find_next_time_expression_time 30s into the future."""
    tz = dt_util.get_time_zone("America/Chicago")
    dt_util.set_default_time_zone(tz)

    # Leaving DST, clocks are rolled back

    # Move ahead 30 seconds not folded yet
    hour_minute_second = (1, 30, 31)
    test_time = datetime(2021, 11, 7, 1, 30, 1, tzinfo=tz, fold=0)
    matching_hours, matching_minutes, matching_seconds = _get_matches(
        *hour_minute_second
    )
    next_time = dt_util.find_next_time_expression_time(
        test_time, matching_seconds, matching_minutes, matching_hours
    )
    assert next_time == datetime(2021, 11, 7, 1, 30, 31, tzinfo=tz, fold=0)
    assert dt_util.as_utc(next_time) == datetime(
        2021, 11, 7, 6, 30, 31, tzinfo=dt_util.UTC
    )
    assert next_time.fold == 0


def test_find_next_time_expression_time_leave_dst_chicago_before_the_fold_same_time() -> (
    None
):
    """Test leaving daylight saving time for find_next_time_expression_time with the same time."""
    tz = dt_util.get_time_zone("America/Chicago")
    dt_util.set_default_time_zone(tz)

    # Leaving DST, clocks are rolled back

    # Move to the same time not folded yet
    hour_minute_second = (0, 30, 1)
    test_time = datetime(2021, 11, 7, *hour_minute_second, tzinfo=tz, fold=0)
    matching_hours, matching_minutes, matching_seconds = _get_matches(
        *hour_minute_second
    )
    next_time = dt_util.find_next_time_expression_time(
        test_time, matching_seconds, matching_minutes, matching_hours
    )
    assert next_time == datetime(2021, 11, 7, *hour_minute_second, tzinfo=tz, fold=0)
    assert dt_util.as_utc(next_time) == datetime(
        2021, 11, 7, 5, 30, 1, tzinfo=dt_util.UTC
    )
    assert next_time.fold == 0


def test_find_next_time_expression_time_leave_dst_chicago_into_the_fold_same_time() -> (
    None
):
    """Test leaving daylight saving time for find_next_time_expression_time."""
    tz = dt_util.get_time_zone("America/Chicago")
    dt_util.set_default_time_zone(tz)

    # Leaving DST, clocks are rolled back

    # Find the same time inside the fold
    hour_minute_second = (1, 30, 1)
    test_time = datetime(2021, 11, 7, *hour_minute_second, tzinfo=tz, fold=0)
    matching_hours, matching_minutes, matching_seconds = _get_matches(
        *hour_minute_second
    )

    next_time = dt_util.find_next_time_expression_time(
        test_time, matching_seconds, matching_minutes, matching_hours
    )
    assert next_time == datetime(2021, 11, 7, *hour_minute_second, tzinfo=tz, fold=1)
    assert next_time.fold == 0
    assert dt_util.as_utc(next_time) == datetime(
        2021, 11, 7, 6, 30, 1, tzinfo=dt_util.UTC
    )


def test_find_next_time_expression_time_leave_dst_chicago_into_the_fold_ahead_1_hour_10_min() -> (
    None
):
    """Test leaving daylight saving time for find_next_time_expression_time."""
    tz = dt_util.get_time_zone("America/Chicago")
    dt_util.set_default_time_zone(tz)

    # Leaving DST, clocks are rolled back

    # Find 1h 10m after into the fold
    # Start at 01:30:01 fold=0
    # Reach to 01:20:01 fold=1
    hour_minute_second = (1, 20, 1)
    test_time = datetime(2021, 11, 7, 1, 30, 1, tzinfo=tz, fold=0)
    matching_hours, matching_minutes, matching_seconds = _get_matches(
        *hour_minute_second
    )

    next_time = dt_util.find_next_time_expression_time(
        test_time, matching_seconds, matching_minutes, matching_hours
    )
    assert next_time == datetime(2021, 11, 7, *hour_minute_second, tzinfo=tz, fold=1)
    assert next_time.fold == 1  # time is ambiguous
    assert dt_util.as_utc(next_time) == datetime(
        2021, 11, 7, 7, 20, 1, tzinfo=dt_util.UTC
    )


def test_find_next_time_expression_time_leave_dst_chicago_inside_the_fold_ahead_10_min() -> (
    None
):
    """Test leaving daylight saving time for find_next_time_expression_time."""
    tz = dt_util.get_time_zone("America/Chicago")
    dt_util.set_default_time_zone(tz)

    # Leaving DST, clocks are rolled back

    # Find 10m later while we are in the fold
    # Start at 01:30:01 fold=0
    # Reach to 01:40:01 fold=1
    hour_minute_second = (1, 40, 1)
    test_time = datetime(2021, 11, 7, 1, 30, 1, tzinfo=tz, fold=1)
    matching_hours, matching_minutes, matching_seconds = _get_matches(
        *hour_minute_second
    )

    next_time = dt_util.find_next_time_expression_time(
        test_time, matching_seconds, matching_minutes, matching_hours
    )
    assert next_time == datetime(2021, 11, 7, *hour_minute_second, tzinfo=tz, fold=1)
    assert next_time.fold == 1  # time is ambiguous
    assert dt_util.as_utc(next_time) == datetime(
        2021, 11, 7, 7, 40, 1, tzinfo=dt_util.UTC
    )


def test_find_next_time_expression_time_leave_dst_chicago_past_the_fold_ahead_2_hour_10_min() -> (
    None
):
    """Test leaving daylight saving time for find_next_time_expression_time."""
    tz = dt_util.get_time_zone("America/Chicago")
    dt_util.set_default_time_zone(tz)

    # Leaving DST, clocks are rolled back

    # Find 1h 10m after into the fold
    # Start at 01:30:01 fold=0
    # Reach to 02:20:01 past the fold
    hour_minute_second = (2, 20, 1)
    test_time = datetime(2021, 11, 7, 1, 30, 1, tzinfo=tz, fold=0)
    matching_hours, matching_minutes, matching_seconds = _get_matches(
        *hour_minute_second
    )

    next_time = dt_util.find_next_time_expression_time(
        test_time, matching_seconds, matching_minutes, matching_hours
    )
    assert next_time == datetime(2021, 11, 7, *hour_minute_second, tzinfo=tz, fold=1)
    assert next_time.fold == 0  # Time is no longer ambiguous
    assert dt_util.as_utc(next_time) == datetime(
        2021, 11, 7, 8, 20, 1, tzinfo=dt_util.UTC
    )


def test_find_next_time_expression_microseconds() -> None:
    """Test finding next time expression with microsecond clock drift."""
    hour_minute_second = (None, "5", "10")
    test_time = datetime(2022, 5, 13, 0, 5, 9, tzinfo=dt_util.UTC)
    matching_hours, matching_minutes, matching_seconds = _get_matches(
        *hour_minute_second
    )
    next_time = dt_util.find_next_time_expression_time(
        test_time, matching_seconds, matching_minutes, matching_hours
    )
    assert next_time == datetime(2022, 5, 13, 0, 5, 10, tzinfo=dt_util.UTC)
    next_time_last_microsecond_plus_one = next_time.replace(
        microsecond=999999
    ) + timedelta(seconds=1)
    time_after = dt_util.find_next_time_expression_time(
        next_time_last_microsecond_plus_one,
        matching_seconds,
        matching_minutes,
        matching_hours,
    )
    assert time_after == datetime(2022, 5, 13, 1, 5, 10, tzinfo=dt_util.UTC)


def test_find_next_time_expression_tenth_second_pattern_does_not_drift_entering_dst() -> (
    None
):
    """Test finding next time expression tenth second pattern does not drift entering dst."""
    tz = dt_util.get_time_zone("America/Chicago")
    dt_util.set_default_time_zone(tz)
    tenth_second_pattern = (None, None, "10")
    # Entering DST, clocks go forward
    test_time = datetime(2021, 3, 15, 2, 30, 0, tzinfo=tz, fold=0)
    matching_hours, matching_minutes, matching_seconds = _get_matches(
        *tenth_second_pattern
    )
    next_time = dt_util.find_next_time_expression_time(
        test_time, matching_seconds, matching_minutes, matching_hours
    )
    assert next_time == datetime(2021, 3, 15, 2, 30, 10, tzinfo=tz)
    prev_target = next_time
    for _ in range(1000):
        next_target = dt_util.find_next_time_expression_time(
            prev_target.replace(microsecond=999999) + timedelta(seconds=1),
            matching_seconds,
            matching_minutes,
            matching_hours,
        )
        assert (next_target - prev_target).total_seconds() == 60
        assert next_target.second == 10
        prev_target = next_target
