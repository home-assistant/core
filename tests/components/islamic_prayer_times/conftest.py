"""conftest bla bla."""
from unittest.mock import patch

import pytest

from . import PRAYER_TIMES


@pytest.fixture(autouse=True)
def mock_api():
    """Mock islamic_prayer api."""
    with patch(
        "prayer_times_calculator.PrayerTimesCalculator.fetch_prayer_times",
        return_value=PRAYER_TIMES,
    ) as mock_object:
        yield mock_object
