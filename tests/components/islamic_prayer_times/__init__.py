"""Tests for the islamic_prayer_times component."""

from datetime import datetime

import homeassistant.util.dt as dt_util

PRAYER_TIMES = {
    "Fajr": "06:10",
    "Sunrise": "07:25",
    "Dhuhr": "12:30",
    "Asr": "15:32",
    "Maghrib": "17:35",
    "Isha": "18:53",
    "Midnight": "00:45",
}

PRAYER_TIMES_TIMESTAMPS = {
    "Fajr": datetime(2020, 1, 1, 6, 10, 0, tzinfo=dt_util.UTC),
    "Sunrise": datetime(2020, 1, 1, 7, 25, 0, tzinfo=dt_util.UTC),
    "Dhuhr": datetime(2020, 1, 1, 12, 30, 0, tzinfo=dt_util.UTC),
    "Asr": datetime(2020, 1, 1, 15, 32, 0, tzinfo=dt_util.UTC),
    "Maghrib": datetime(2020, 1, 1, 17, 35, 0, tzinfo=dt_util.UTC),
    "Isha": datetime(2020, 1, 1, 18, 53, 0, tzinfo=dt_util.UTC),
    "Midnight": datetime(2020, 1, 1, 00, 45, 0, tzinfo=dt_util.UTC),
}

NEW_PRAYER_TIMES = {
    "Fajr": "06:00",
    "Sunrise": "07:25",
    "Dhuhr": "12:30",
    "Asr": "15:32",
    "Maghrib": "17:45",
    "Isha": "18:53",
    "Midnight": "00:43",
}

NEW_PRAYER_TIMES_TIMESTAMPS = {
    "Fajr": datetime(2020, 1, 1, 6, 00, 0, tzinfo=dt_util.UTC),
    "Sunrise": datetime(2020, 1, 1, 7, 25, 0, tzinfo=dt_util.UTC),
    "Dhuhr": datetime(2020, 1, 1, 12, 30, 0, tzinfo=dt_util.UTC),
    "Asr": datetime(2020, 1, 1, 15, 32, 0, tzinfo=dt_util.UTC),
    "Maghrib": datetime(2020, 1, 1, 17, 45, 0, tzinfo=dt_util.UTC),
    "Isha": datetime(2020, 1, 1, 18, 53, 0, tzinfo=dt_util.UTC),
    "Midnight": datetime(2020, 1, 1, 00, 43, 0, tzinfo=dt_util.UTC),
}

NOW = datetime(2020, 1, 1, 00, 00, 0, tzinfo=dt_util.UTC)
