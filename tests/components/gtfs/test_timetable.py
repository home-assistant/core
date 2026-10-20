"""Tests for the GTFS timetable."""

from collections.abc import Iterator
from contextlib import contextmanager
import datetime as dt
from pathlib import Path
import threading

import pygtfs
import pytest

from homeassistant.components.gtfs.feed import close_feed, import_feed, open_feed
from homeassistant.components.gtfs.timetable import departures, feed_time_zone
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import FIXTURE_DIR, build_feed_zip

NEW_YORK = dt_util.get_time_zone("America/New_York")


@pytest.fixture(autouse=True)
async def time_zone(hass: HomeAssistant) -> None:
    """Run in a time zone other than the feed's."""
    await hass.config.async_set_time_zone("US/Pacific")


@contextmanager
def _schedule(
    directory: Path, replace: dict[str, str] | None = None
) -> Iterator[pygtfs.Schedule]:
    zip_path = directory / "feed.zip"
    zip_path.write_bytes(build_feed_zip(replace=replace))
    db_path = directory / "feed.sqlite"
    import_feed(zip_path, db_path, threading.Event())
    feed = open_feed(db_path)
    try:
        yield feed.schedule
    finally:
        close_feed(feed)


def _fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text()


def _ny(day: int, hour: int, minute: int = 0, month: int = 10) -> dt.datetime:
    return dt.datetime(2026, month, day, hour, minute, tzinfo=NEW_YORK)


def _summary(
    schedule: pygtfs.Schedule,
    origin: str,
    destination: str,
    start: dt.datetime,
    end: dt.datetime,
) -> list[tuple[str, str, str]]:
    return [
        (item.departure.isoformat(), item.arrival.isoformat(), item.trip_id)
        for item in departures(schedule, origin, destination, start, end, NEW_YORK)
    ]


@pytest.mark.parametrize(
    ("origin", "destination", "start", "end", "expected"),
    [
        pytest.param(
            "S1",
            "S3",
            _ny(19, 0),
            _ny(20, 0),
            [
                ("2026-10-19T12:00:00+00:00", "2026-10-19T12:20:00+00:00", "T1"),
                ("2026-10-19T21:00:00+00:00", "2026-10-19T21:20:00+00:00", "T2"),
            ],
            id="one_day",
        ),
        pytest.param(
            "S1",
            "S3",
            _ny(19, 8, 10),
            _ny(19, 9),
            [("2026-10-19T12:00:00+00:00", "2026-10-19T12:20:00+00:00", "T1")],
            id="trip_in_progress",
        ),
        pytest.param(
            "N1",
            "N2",
            _ny(19, 20),
            _ny(20, 2),
            [("2026-10-20T04:30:00+00:00", "2026-10-20T04:50:00+00:00", "NT1")],
            id="past_midnight_on_previous_service_day",
        ),
        pytest.param(
            "S1",
            "S3",
            dt.datetime(2026, 10, 19, 4, tzinfo=dt.UTC),
            dt.datetime(2026, 10, 20, 4, tzinfo=dt.UTC),
            [
                ("2026-10-19T12:00:00+00:00", "2026-10-19T12:20:00+00:00", "T1"),
                ("2026-10-19T21:00:00+00:00", "2026-10-19T21:20:00+00:00", "T2"),
            ],
            id="utc_window",
        ),
        pytest.param("S1", "S3", _ny(21, 0), _ny(22, 0), [], id="service_removed"),
        pytest.param("S3", "S1", _ny(19, 0), _ny(20, 0), [], id="wrong_direction"),
        pytest.param(
            "S1",
            "S3",
            _ny(1, 0, month=11),
            _ny(1, 12, month=11),
            [("2026-11-01T13:00:00+00:00", "2026-11-01T13:20:00+00:00", "T1")],
            id="dst_end",
        ),
    ],
)
def test_departures(
    tmp_path: Path,
    origin: str,
    destination: str,
    start: dt.datetime,
    end: dt.datetime,
    expected: list[tuple[str, str, str]],
) -> None:
    """Test departures between two stops in a window."""
    with _schedule(tmp_path) as schedule:
        assert _summary(schedule, origin, destination, start, end) == expected


def test_departures_service_added(tmp_path: Path) -> None:
    """Test a service that only runs on a date added by calendar_dates."""
    replace = {
        "calendar_dates.txt": _fixture("calendar_dates.txt") + "EXTRA,20261021,1\n",
        "trips.txt": _fixture("trips.txt") + "R1,EXTRA,T3\n",
        "stop_times.txt": _fixture("stop_times.txt")
        + "T3,12:00:00,12:00:00,S1,1\nT3,12:20:00,12:20:00,S3,2\n",
    }
    with _schedule(tmp_path, replace) as schedule:
        assert _summary(schedule, "S1", "S3", _ny(21, 0), _ny(22, 0)) == [
            ("2026-10-21T16:00:00+00:00", "2026-10-21T16:20:00+00:00", "T3")
        ]


def test_departures_dst_start_service_day(tmp_path: Path) -> None:
    """Test a trip whose service day starts before the window ends.

    When clocks go forward, the service day starts at 23:00 the day before.
    """
    replace = {
        "trips.txt": _fixture("trips.txt") + "R1,DAILY,T9\n",
        "stop_times.txt": _fixture("stop_times.txt")
        + "T9,00:30:00,00:30:00,S1,1\nT9,00:50:00,00:50:00,S3,2\n",
    }
    with _schedule(tmp_path, replace) as schedule:
        assert _summary(
            schedule, "S1", "S3", _ny(7, 23, month=3), _ny(7, 23, 59, month=3)
        ) == [("2026-03-08T04:30:00+00:00", "2026-03-08T04:50:00+00:00", "T9")]


def test_departures_service_ends_in_window(tmp_path: Path) -> None:
    """Test a service whose end date falls inside the window."""
    calendar = (
        "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,"
        "start_date,end_date\n"
        "DAILY,1,1,1,1,1,1,1,20260101,20261019\n"
    )
    with _schedule(tmp_path, {"calendar.txt": calendar}) as schedule:
        assert _summary(schedule, "S1", "S3", _ny(19, 0), _ny(21, 0)) == [
            ("2026-10-19T12:00:00+00:00", "2026-10-19T12:20:00+00:00", "T1"),
            ("2026-10-19T21:00:00+00:00", "2026-10-19T21:20:00+00:00", "T2"),
        ]


def test_departures_trip_visiting_origin_twice(tmp_path: Path) -> None:
    """Test that a trip visiting the origin twice departs from the last visit."""
    replace = {
        "trips.txt": _fixture("trips.txt") + "R1,DAILY,T9\n",
        "stop_times.txt": _fixture("stop_times.txt")
        + "T9,10:00:00,10:00:00,S1,1\nT9,10:10:00,10:10:00,S2,2\n"
        + "T9,10:20:00,10:20:00,S1,3\nT9,10:30:00,10:30:00,S3,4\n",
    }
    with _schedule(tmp_path, replace) as schedule:
        assert _summary(schedule, "S1", "S3", _ny(19, 9), _ny(19, 12)) == [
            ("2026-10-19T14:20:00+00:00", "2026-10-19T14:30:00+00:00", "T9")
        ]


def test_departures_trip_visiting_destination_twice(tmp_path: Path) -> None:
    """Test that a trip visiting the destination twice arrives on its first visit."""
    replace = {
        "trips.txt": _fixture("trips.txt") + "R1,DAILY,T9\n",
        "stop_times.txt": _fixture("stop_times.txt")
        + "T9,10:00:00,10:00:00,S1,1\nT9,10:20:00,10:20:00,S3,2\n"
        + "T9,10:30:00,10:30:00,S2,3\nT9,10:50:00,10:50:00,S3,4\n",
    }
    with _schedule(tmp_path, replace) as schedule:
        assert _summary(schedule, "S1", "S3", _ny(19, 9), _ny(19, 12)) == [
            ("2026-10-19T14:00:00+00:00", "2026-10-19T14:20:00+00:00", "T9")
        ]


def test_departures_pickup_and_drop_off_restrictions(tmp_path: Path) -> None:
    """Test trips that can't be boarded at the origin or left at the destination."""
    stop_times = (
        "trip_id,arrival_time,departure_time,stop_id,stop_sequence,"
        "pickup_type,drop_off_type\n"
        "T1,08:00:00,08:00:00,S1,1,1,0\n"
        "T1,08:20:00,08:20:00,S3,2,0,0\n"
        "T2,17:00:00,17:00:00,S1,1,0,0\n"
        "T2,17:20:00,17:20:00,S3,2,0,1\n"
        "NT1,24:30:00,24:30:00,N1,1,0,0\n"
        "NT1,24:50:00,24:50:00,N2,2,0,0\n"
    )
    with _schedule(tmp_path, {"stop_times.txt": stop_times}) as schedule:
        assert _summary(schedule, "S1", "S3", _ny(19, 0), _ny(20, 0)) == []


def test_departure_details(tmp_path: Path) -> None:
    """Test the route, headsign, agency and service date of a departure."""
    with _schedule(tmp_path) as schedule:
        (departure,) = departures(
            schedule, "N1", "N2", _ny(19, 20), _ny(20, 2), NEW_YORK
        )
    assert departure.service_date == dt.date(2026, 10, 19)
    assert departure.route_short_name == "N"
    assert departure.route_long_name == "Night Owl"
    assert departure.headsign is None
    assert departure.agency_name == "Test Agency"


@pytest.mark.parametrize(
    ("agency_timezone", "expected"),
    [
        pytest.param("America/New_York", "America/New_York", id="feed"),
        pytest.param("Not/AZone", "US/Pacific", id="invalid_falls_back"),
    ],
)
def test_feed_time_zone(tmp_path: Path, agency_timezone: str, expected: str) -> None:
    """Test the feed time zone and the fallback to Home Assistant's."""
    agency = (
        "agency_id,agency_name,agency_url,agency_timezone\n"
        f"TA,Test Agency,https://example.com,{agency_timezone}\n"
    )
    with _schedule(tmp_path, {"agency.txt": agency}) as schedule:
        assert str(feed_time_zone(schedule)) == expected
