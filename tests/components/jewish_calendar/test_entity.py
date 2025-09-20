"""The tests for the Jewish calendar entity base class."""

import datetime as dt

from hdate import Location, Zmanim

from homeassistant.components.jewish_calendar.entity import (
    JewishCalendarData,
    JewishCalendarEntity,
)
from homeassistant.util import dt as dt_util


class JewishCalendarEntityTest(JewishCalendarEntity):
    """Test class for JewishCalendarEntity."""

    def __init__(self) -> None:  # pylint: disable=super-init-not-called
        """Initialize the test entity."""
        self.data = JewishCalendarData(
            language="he",
            diaspora=False,
            location=Location(),
            candle_lighting_offset=18,
            havdalah_offset=34,
        )

    def _update_times(self, zmanim: Zmanim) -> list[dt.datetime | None]:
        """Mock update times method."""
        return []


def test_zmanim_cache() -> None:
    """Test the caching mechanism of zmanim."""
    today = dt_util.now().date()
    assert JewishCalendarEntityTest().make_zmanim(
        today
    ) is JewishCalendarEntityTest().make_zmanim(today)


def test_results_cache() -> None:
    """Test the caching mechanism of create_results."""
    now = dt_util.now()
    x = JewishCalendarEntityTest()
    x.create_results(now)
    y = JewishCalendarEntityTest()
    y.create_results(now)
    assert x.data.results is y.data.results
