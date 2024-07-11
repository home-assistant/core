"""Tests for the jewish_calendar component."""

from collections import namedtuple
from datetime import datetime

from freezegun import freeze_time as alter_time  # noqa: F401

from homeassistant.components import jewish_calendar
import homeassistant.util.dt as dt_util

_LatLng = namedtuple("_LatLng", ["lat", "lng"])

HDATE_DEFAULT_ALTITUDE = 754
NYC_LATLNG = _LatLng(40.7128, -74.0060)
JERUSALEM_LATLNG = _LatLng(31.778, 35.235)


def make_nyc_test_params(dtime, results, havdalah_offset=0):
    """Make test params for NYC."""
    if isinstance(results, dict):
        time_zone = dt_util.get_time_zone("America/New_York")
        results = {
            key: value.replace(tzinfo=time_zone)
            if isinstance(value, datetime)
            else value
            for key, value in results.items()
        }
    return (
        dtime,
        jewish_calendar.DEFAULT_CANDLE_LIGHT,
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
            key: value.replace(tzinfo=time_zone)
            if isinstance(value, datetime)
            else value
            for key, value in results.items()
        }
    return (
        dtime,
        jewish_calendar.DEFAULT_CANDLE_LIGHT,
        havdalah_offset,
        False,
        "Asia/Jerusalem",
        JERUSALEM_LATLNG.lat,
        JERUSALEM_LATLNG.lng,
        results,
    )
