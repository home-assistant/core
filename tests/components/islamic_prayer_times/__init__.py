"""Tests for the islamic_prayer_times component."""

from datetime import datetime

from homeassistant.const import CONF_LATITUDE, CONF_LOCATION, CONF_LONGITUDE, CONF_NAME
from homeassistant.util import dt as dt_util

MOCK_USER_INPUT = {
    CONF_NAME: "Home",
    CONF_LOCATION: {CONF_LATITUDE: 12.34, CONF_LONGITUDE: 23.45},
}

MOCK_CONFIG = {CONF_LATITUDE: 12.34, CONF_LONGITUDE: 23.45}


PRAYER_TIMES_YESTERDAY = {
    "Fajr": "2019-12-31T06:09:00+00:00",
    "Sunrise": "2019-12-31T07:24:00+00:00",
    "Dhuhr": "2019-12-31T12:29:00+00:00",
    "Asr": "2019-12-31T15:31:00+00:00",
    "Maghrib": "2019-12-31T17:34:00+00:00",
    "Isha": "2019-12-31T18:52:00+00:00",
    "Midnight": "2020-01-01T00:44:00+00:00",
}

PRAYER_TIMES = {
    "Fajr": "2020-01-01T06:10:00+00:00",
    "Sunrise": "2020-01-01T07:25:00+00:00",
    "Dhuhr": "2020-01-01T12:30:00+00:00",
    "Asr": "2020-01-01T15:32:00+00:00",
    "Maghrib": "2020-01-01T17:35:00+00:00",
    "Isha": "2020-01-01T18:53:00+00:00",
    "Midnight": "2020-01-02T00:45:00+00:00",
}

PRAYER_TIMES_TOMORROW = {
    "Fajr": "2020-01-02T06:11:00+00:00",
    "Sunrise": "2020-01-02T07:26:00+00:00",
    "Dhuhr": "2020-01-02T12:31:00+00:00",
    "Asr": "2020-01-02T15:33:00+00:00",
    "Maghrib": "2020-01-02T17:36:00+00:00",
    "Isha": "2020-01-02T18:54:00+00:00",
    "Midnight": "2020-01-03T00:46:00+00:00",
}

NOW = datetime(2020, 1, 1, 00, 00, 0, tzinfo=dt_util.UTC)
