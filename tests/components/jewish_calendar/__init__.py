"""Tests for the jewish_calendar component."""
from collections import namedtuple
from contextlib import contextmanager
from unittest.mock import patch

from homeassistant.components import jewish_calendar


_LatLng = namedtuple("_LatLng", ["lat", "lng"])

NYC_LATLNG = _LatLng(40.7128, -74.0060)
JERUSALEM_LATLNG = _LatLng(31.778, 35.235)


def make_nyc_test_params(dtime, results, havdalah_offset=0):
    """Make test params for NYC."""
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
def alter_time(retval):
    """Manage multiple time mocks."""
    patch1 = patch("homeassistant.util.dt.utcnow", return_value=retval)
    patch2 = patch("homeassistant.util.dt.now", return_value=retval)

    with patch1, patch2:
        yield
