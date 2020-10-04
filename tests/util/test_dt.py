"""Test Home Assistant date util methods."""
from datetime import datetime, timedelta

import pytest

import homeassistant.util.dt as dt_util

DEFAULT_TIME_ZONE = dt_util.DEFAULT_TIME_ZONE
TEST_TIME_ZONE = "America/Los_Angeles"


def teardown():
    """Stop everything that was started."""
    dt_util.set_default_time_zone(DEFAULT_TIME_ZONE)


def test_get_time_zone_retrieves_valid_time_zone():
    """Test getting a time zone."""
    time_zone = dt_util.get_time_zone(TEST_TIME_ZONE)

    assert time_zone is not None
    assert TEST_TIME_ZONE == time_zone.zone


def test_get_time_zone_returns_none_for_garbage_time_zone():
    """Test getting a non existing time zone."""
    time_zone = dt_util.get_time_zone("Non existing time zone")

    assert time_zone is None


def test_set_default_time_zone():
    """Test setting default time zone."""
    time_zone = dt_util.get_time_zone(TEST_TIME_ZONE)

    dt_util.set_default_time_zone(time_zone)

    # We cannot compare the timezones directly because of DST
    assert time_zone.zone == dt_util.now().tzinfo.zone


def test_utcnow():
    """Test the UTC now method."""
    assert abs(dt_util.utcnow().replace(tzinfo=None) - datetime.utcnow()) < timedelta(
        seconds=1
    )


def test_now():
    """Test the now method."""
    dt_util.set_default_time_zone(dt_util.get_time_zone(TEST_TIME_ZONE))

    assert abs(
        dt_util.as_utc(dt_util.now()).replace(tzinfo=None) - datetime.utcnow()
    ) < timedelta(seconds=1)


def test_as_utc_with_naive_object():
    """Test the now method."""
    utcnow = datetime.utcnow()

    assert utcnow == dt_util.as_utc(utcnow).replace(tzinfo=None)


def test_as_utc_with_utc_object():
    """Test UTC time with UTC object."""
    utcnow = dt_util.utcnow()

    assert utcnow == dt_util.as_utc(utcnow)


def test_as_utc_with_local_object():
    """Test the UTC time with local object."""
    dt_util.set_default_time_zone(dt_util.get_time_zone(TEST_TIME_ZONE))
    localnow = dt_util.now()
    utcnow = dt_util.as_utc(localnow)

    assert localnow == utcnow
    assert localnow.tzinfo != utcnow.tzinfo


def test_as_local_with_naive_object():
    """Test local time with native object."""
    now = dt_util.now()
    assert abs(now - dt_util.as_local(datetime.utcnow())) < timedelta(seconds=1)


def test_as_local_with_local_object():
    """Test local with local object."""
    now = dt_util.now()
    assert now == now


def test_as_local_with_utc_object():
    """Test local time with UTC object."""
    dt_util.set_default_time_zone(dt_util.get_time_zone(TEST_TIME_ZONE))

    utcnow = dt_util.utcnow()
    localnow = dt_util.as_local(utcnow)

    assert localnow == utcnow
    assert localnow.tzinfo != utcnow.tzinfo


def test_utc_from_timestamp():
    """Test utc_from_timestamp method."""
    assert datetime(1986, 7, 9, tzinfo=dt_util.UTC) == dt_util.utc_from_timestamp(
        521251200
    )


def test_as_timestamp():
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


def test_parse_datetime_converts_correctly():
    """Test parse_datetime converts strings."""
    assert datetime(1986, 7, 9, 12, 0, 0, tzinfo=dt_util.UTC) == dt_util.parse_datetime(
        "1986-07-09T12:00:00Z"
    )

    utcnow = dt_util.utcnow()

    assert utcnow == dt_util.parse_datetime(utcnow.isoformat())


def test_parse_datetime_returns_none_for_incorrect_format():
    """Test parse_datetime returns None if incorrect format."""
    assert dt_util.parse_datetime("not a datetime string") is None


def test_get_age():
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


def test_parse_time_expression():
    """Test parse_time_expression."""
    assert [x for x in range(60)] == dt_util.parse_time_expression("*", 0, 59)
    assert [x for x in range(60)] == dt_util.parse_time_expression(None, 0, 59)

    assert [x for x in range(0, 60, 5)] == dt_util.parse_time_expression("/5", 0, 59)

    assert [1, 2, 3] == dt_util.parse_time_expression([2, 1, 3], 0, 59)

    assert [x for x in range(24)] == dt_util.parse_time_expression("*", 0, 23)

    assert [42] == dt_util.parse_time_expression(42, 0, 59)

    with pytest.raises(ValueError):
        dt_util.parse_time_expression(61, 0, 60)


def test_find_next_time_expression_time_basic():
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


def test_find_next_time_expression_time_dst():
    """Test daylight saving time for find_next_time_expression_time."""
    tz = dt_util.get_time_zone("Europe/Vienna")
    dt_util.set_default_time_zone(tz)

    def find(dt, hour, minute, second):
        """Call test_find_next_time_expression_time."""
        seconds = dt_util.parse_time_expression(second, 0, 59)
        minutes = dt_util.parse_time_expression(minute, 0, 59)
        hours = dt_util.parse_time_expression(hour, 0, 23)

        return dt_util.find_next_time_expression_time(dt, seconds, minutes, hours)

    # Entering DST, clocks are rolled forward
    assert tz.localize(datetime(2018, 3, 26, 2, 30, 0)) == find(
        tz.localize(datetime(2018, 3, 25, 1, 50, 0)), 2, 30, 0
    )

    assert tz.localize(datetime(2018, 3, 26, 2, 30, 0)) == find(
        tz.localize(datetime(2018, 3, 25, 3, 50, 0)), 2, 30, 0
    )

    assert tz.localize(datetime(2018, 3, 26, 2, 30, 0)) == find(
        tz.localize(datetime(2018, 3, 26, 1, 50, 0)), 2, 30, 0
    )

    # Leaving DST, clocks are rolled back
    assert tz.localize(datetime(2018, 10, 28, 2, 30, 0), is_dst=False) == find(
        tz.localize(datetime(2018, 10, 28, 2, 5, 0), is_dst=False), 2, 30, 0
    )

    assert tz.localize(datetime(2018, 10, 28, 2, 30, 0), is_dst=False) == find(
        tz.localize(datetime(2018, 10, 28, 2, 55, 0), is_dst=True), 2, 30, 0
    )

    assert tz.localize(datetime(2018, 10, 28, 4, 30, 0), is_dst=False) == find(
        tz.localize(datetime(2018, 10, 28, 2, 55, 0), is_dst=True), 4, 30, 0
    )

    assert tz.localize(datetime(2018, 10, 28, 2, 30, 0), is_dst=True) == find(
        tz.localize(datetime(2018, 10, 28, 2, 5, 0), is_dst=True), 2, 30, 0
    )

    assert tz.localize(datetime(2018, 10, 29, 2, 30, 0)) == find(
        tz.localize(datetime(2018, 10, 28, 2, 55, 0), is_dst=False), 2, 30, 0
    )
