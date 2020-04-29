"""Tests for the islamic_prayer_times component."""

from datetime import datetime

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
    "Fajr": datetime(2020, 1, 1, 6, 10, 0),
    "Sunrise": datetime(2020, 1, 1, 7, 25, 0),
    "Dhuhr": datetime(2020, 1, 1, 12, 30, 0),
    "Asr": datetime(2020, 1, 1, 15, 32, 0),
    "Maghrib": datetime(2020, 1, 1, 17, 35, 0),
    "Isha": datetime(2020, 1, 1, 18, 53, 0),
    "Midnight": datetime(2020, 1, 1, 00, 45, 0),
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
    "Fajr": datetime(2020, 1, 1, 6, 00, 0),
    "Sunrise": datetime(2020, 1, 1, 7, 25, 0),
    "Dhuhr": datetime(2020, 1, 1, 12, 30, 0),
    "Asr": datetime(2020, 1, 1, 15, 32, 0),
    "Maghrib": datetime(2020, 1, 1, 17, 45, 0),
    "Isha": datetime(2020, 1, 1, 18, 53, 0),
    "Midnight": datetime(2020, 1, 1, 00, 43, 0),
}

NOW = datetime(2020, 1, 1, 00, 00, 0)
