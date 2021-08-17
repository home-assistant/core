"""Tests for the islamic_prayer_times component."""

import datetime as dt

PRAYER_TIMES = {
    "Imsak": "06:00",
    "Fajr": "06:10",
    "Sunrise": "07:25",
    "Dhuhr": "12:30",
    "Asr": "15:32",
    "Maghrib": "17:35",
    "Isha": "18:53",
    "Midnight": "00:45",
}

PRAYER_TIMES_TIMESTAMPS = {
    "Imsak": dt.datetime(2020, 1, 1, 6, 0, 0, tzinfo=dt.timezone.utc),
    "Fajr": dt.datetime(2020, 1, 1, 6, 10, 0, tzinfo=dt.timezone.utc),
    "Sunrise": dt.datetime(2020, 1, 1, 7, 25, 0, tzinfo=dt.timezone.utc),
    "Dhuhr": dt.datetime(2020, 1, 1, 12, 30, 0, tzinfo=dt.timezone.utc),
    "Asr": dt.datetime(2020, 1, 1, 15, 32, 0, tzinfo=dt.timezone.utc),
    "Maghrib": dt.datetime(2020, 1, 1, 17, 35, 0, tzinfo=dt.timezone.utc),
    "Isha": dt.datetime(2020, 1, 1, 18, 53, 0, tzinfo=dt.timezone.utc),
    "Midnight": dt.datetime(2020, 1, 1, 00, 45, 0, tzinfo=dt.timezone.utc),
}

NEW_PRAYER_TIMES = {
    "Imsak": "05:50",
    "Fajr": "06:00",
    "Sunrise": "07:25",
    "Dhuhr": "12:30",
    "Asr": "15:32",
    "Maghrib": "17:45",
    "Isha": "18:53",
    "Midnight": "00:43",
}

NEW_PRAYER_TIMES_TIMESTAMPS = {
    "Imsak": dt.datetime(2020, 1, 1, 5, 50, 0, tzinfo=dt.timezone.utc),
    "Fajr": dt.datetime(2020, 1, 1, 6, 00, 0, tzinfo=dt.timezone.utc),
    "Sunrise": dt.datetime(2020, 1, 1, 7, 25, 0, tzinfo=dt.timezone.utc),
    "Dhuhr": dt.datetime(2020, 1, 1, 12, 30, 0, tzinfo=dt.timezone.utc),
    "Asr": dt.datetime(2020, 1, 1, 15, 32, 0, tzinfo=dt.timezone.utc),
    "Maghrib": dt.datetime(2020, 1, 1, 17, 45, 0, tzinfo=dt.timezone.utc),
    "Isha": dt.datetime(2020, 1, 1, 18, 53, 0, tzinfo=dt.timezone.utc),
    "Midnight": dt.datetime(2020, 1, 1, 00, 43, 0, tzinfo=dt.timezone.utc),
}

NOW = dt.datetime(2020, 1, 1, 00, 00, 0).astimezone()
