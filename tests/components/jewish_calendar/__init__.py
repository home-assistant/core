"""Tests for the jewish_calendar component."""
from collections import namedtuple
from contextlib import contextmanager
from datetime import datetime

from homeassistant.components import jewish_calendar
import homeassistant.util.dt as dt_util

from tests.async_mock import patch

_LatLng = namedtuple("_LatLng", ["lat", "lng"])

HDATE_DEFAULT_ALTITUDE = 754
NYC_LATLNG = _LatLng(40.7128, -74.0060)
JERUSALEM_LATLNG = _LatLng(31.778, 35.235)

ORIG_TIME_ZONE = dt_util.DEFAULT_TIME_ZONE


def teardown_module():
    """Reset time zone."""
    dt_util.set_default_time_zone(ORIG_TIME_ZONE)


def make_nyc_test_params(dtime, results, havdalah_offset=0):
    """Make test params for NYC."""
    if isinstance(results, dict):
        time_zone = dt_util.get_time_zone("America/New_York")
        results = {
            key: time_zone.localize(value) if isinstance(value, datetime) else value
            for key, value in results.items()
        }
    return (
        dtime,
        jewish_calendar.CANDLE_LIGHT_DEFAULT,
        havdalah_offset,
        True,
        "America/New_York",
        NYC_LATLNG.lat,
        NYC_LATLNG.lng,
        results,
    )


def make_jerusalem_test_params(dtime, results, havdalah_offset=0):
    """Make test params for Jerusalem."""
    if isinstance(results, dict):
        time_zone = dt_util.get_time_zone("Asia/Jerusalem")
        results = {
            key: time_zone.localize(value) if isinstance(value, datetime) else value
            for key, value in results.items()
        }
    return (
        dtime,
        jewish_calendar.CANDLE_LIGHT_DEFAULT,
        havdalah_offset,
        False,
        "Asia/Jerusalem",
        JERUSALEM_LATLNG.lat,
        JERUSALEM_LATLNG.lng,
        results,
    )


@contextmanager
def alter_time(local_time):
    """Manage multiple time mocks."""
    utc_time = dt_util.as_utc(local_time)
    patch1 = patch("homeassistant.util.dt.utcnow", return_value=utc_time)
    patch2 = patch("homeassistant.util.dt.now", return_value=local_time)

    with patch1, patch2:
        yield
