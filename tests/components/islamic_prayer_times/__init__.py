"""Tests for the islamic_prayer_times component."""
import re
from datetime import datetime

import homeassistant.util.dt as dt_util
from prayer_times_calculator import PrayerTimesCalculator

REQUEST_URL = re.compile(PrayerTimesCalculator.API_URL + ".+")

NOW = datetime(2020, 1, 1, 00, 00, 0, tzinfo=dt_util.UTC)
