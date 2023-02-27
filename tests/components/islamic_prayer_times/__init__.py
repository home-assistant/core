"""Tests for the islamic_prayer_times component."""
from datetime import datetime
import re

from prayer_times_calculator import PrayerTimesCalculator

import homeassistant.util.dt as dt_util

REQUEST_URL = re.compile(PrayerTimesCalculator.API_URL + ".+")

NOW = datetime(2020, 1, 1, 00, 00, 0, tzinfo=dt_util.UTC)
