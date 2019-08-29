"""The tests for the Jewish calendar binary sensors."""
from datetime import timedelta
from datetime import datetime as dt
from unittest.mock import patch

import pytest

from homeassistant.const import STATE_ON, STATE_OFF
import homeassistant.util.dt as dt_util
from homeassistant.setup import async_setup_component
from homeassistant.components import jewish_calendar

from tests.common import async_fire_time_changed

from . import make_nyc_test_params, make_jerusalem_test_params

melacha_params = [
    make_nyc_test_params(dt(2018, 9, 1, 16, 0), STATE_ON),
    make_nyc_test_params(dt(2018, 9, 1, 20, 21), STATE_OFF),
    make_nyc_test_params(dt(2018, 9, 7, 13, 1), STATE_OFF),
    make_nyc_test_params(dt(2018, 9, 8, 21, 25), STATE_OFF),
    make_nyc_test_params(dt(2018, 9, 9, 21, 25), STATE_ON),
    make_nyc_test_params(dt(2018, 9, 10, 21, 25), STATE_ON),
    make_nyc_test_params(dt(2018, 9, 28, 21, 25), STATE_ON),
    make_nyc_test_params(dt(2018, 9, 29, 21, 25), STATE_OFF),
    make_nyc_test_params(dt(2018, 9, 30, 21, 25), STATE_ON),
    make_nyc_test_params(dt(2018, 10, 1, 21, 25), STATE_ON),
    make_jerusalem_test_params(dt(2018, 9, 29, 21, 25), STATE_OFF),
    make_jerusalem_test_params(dt(2018, 9, 30, 21, 25), STATE_ON),
    make_jerusalem_test_params(dt(2018, 10, 1, 21, 25), STATE_OFF),
]

melacha_test_ids = [
    "currently_first_shabbat",
    "after_first_shabbat",
    "friday_upcoming_shabbat",
    "upcoming_rosh_hashana",
    "currently_rosh_hashana",
    "second_day_rosh_hashana",
    "currently_shabbat_chol_hamoed",
    "upcoming_two_day_yomtov_in_diaspora",
    "currently_first_day_of_two_day_yomtov_in_diaspora",
    "currently_second_day_of_two_day_yomtov_in_diaspora",
    "upcoming_one_day_yom_tov_in_israel",
    "currently_one_day_yom_tov_in_israel",
    "after_one_day_yom_tov_in_israel",
]


@pytest.mark.parametrize(
    [
        "now",
        "candle_lighting",
        "havdalah",
        "diaspora",
        "tzname",
        "latitude",
        "longitude",
        "result",
    ],
    melacha_params,
    ids=melacha_test_ids,
)
async def test_issur_melacha_sensor(
    hass, now, candle_lighting, havdalah, diaspora, tzname, latitude, longitude, result
):
    """Test Issur Melacha sensor output."""
    time_zone = dt_util.get_time_zone(tzname)
    test_time = time_zone.localize(now)

    hass.config.time_zone = time_zone
    hass.config.latitude = latitude
    hass.config.longitude = longitude

    assert await async_setup_component(
        hass,
        jewish_calendar.DOMAIN,
        {
            "jewish_calendar": {
                "name": "test",
                "language": "english",
                "diaspora": diaspora,
                "candle_lighting_minutes_before_sunset": candle_lighting,
                "havdalah_minutes_after_sunset": havdalah,
            }
        },
    )
    await hass.async_block_till_done()

    with patch("homeassistant.util.dt.now", return_value=test_time):
        future = dt_util.utcnow() + timedelta(seconds=30)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        assert (
            hass.states.get("binary_sensor.test_issur_melacha_in_effect").state
            == result
        )
