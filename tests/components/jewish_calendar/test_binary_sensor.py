"""The tests for the Jewish calendar binary sensors."""
from datetime import datetime as dt, timedelta

import pytest

from homeassistant.components import jewish_calendar
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from . import (
    HDATE_DEFAULT_ALTITUDE,
    alter_time,
    make_jerusalem_test_params,
    make_nyc_test_params,
)

from tests.async_mock import patch
from tests.common import async_fire_time_changed

MELACHA_PARAMS = [
    make_nyc_test_params(
        dt(2018, 9, 1, 16, 0),
        {
            "state": STATE_ON,
            "update": dt(2018, 9, 1, 20, 14),
        },
    ),
    make_nyc_test_params(
        dt(2018, 9, 1, 20, 21),
        {
            "state": STATE_OFF,
            "update": dt(2018, 9, 2, 6, 21),
        },
    ),
    make_nyc_test_params(
        dt(2018, 9, 7, 13, 1),
        {
            "state": STATE_OFF,
            "update": dt(2018, 9, 7, 19, 4),
        },
    ),
    make_nyc_test_params(
        dt(2018, 9, 8, 21, 25),
        {
            "state": STATE_OFF,
            "update": dt(2018, 9, 9, 6, 27),
        },
    ),
    make_nyc_test_params(
        dt(2018, 9, 9, 21, 25),
        {
            "state": STATE_ON,
            "update": dt(2018, 9, 10, 6, 28),
        },
    ),
    make_nyc_test_params(
        dt(2018, 9, 10, 21, 25),
        {
            "state": STATE_ON,
            "update": dt(2018, 9, 11, 6, 29),
        },
    ),
    make_nyc_test_params(
        dt(2018, 9, 11, 11, 25),
        {
            "state": STATE_ON,
            "update": dt(2018, 9, 11, 19, 57),
        },
    ),
    make_nyc_test_params(
        dt(2018, 9, 29, 16, 25),
        {
            "state": STATE_ON,
            "update": dt(2018, 9, 29, 19, 25),
        },
    ),
    make_nyc_test_params(
        dt(2018, 9, 29, 21, 25),
        {
            "state": STATE_OFF,
            "update": dt(2018, 9, 30, 6, 48),
        },
    ),
    make_nyc_test_params(
        dt(2018, 9, 30, 21, 25),
        {
            "state": STATE_ON,
            "update": dt(2018, 10, 1, 6, 49),
        },
    ),
    make_nyc_test_params(
        dt(2018, 10, 1, 21, 25),
        {
            "state": STATE_ON,
            "update": dt(2018, 10, 2, 6, 50),
        },
    ),
    make_jerusalem_test_params(
        dt(2018, 9, 29, 21, 25),
        {
            "state": STATE_OFF,
            "update": dt(2018, 9, 30, 6, 29),
        },
    ),
    make_jerusalem_test_params(
        dt(2018, 10, 1, 11, 25),
        {
            "state": STATE_ON,
            "update": dt(2018, 10, 1, 19, 2),
        },
    ),
    make_jerusalem_test_params(
        dt(2018, 10, 1, 21, 25),
        {
            "state": STATE_OFF,
            "update": dt(2018, 10, 2, 6, 31),
        },
    ),
]

MELACHA_TEST_IDS = [
    "currently_first_shabbat",
    "after_first_shabbat",
    "friday_upcoming_shabbat",
    "upcoming_rosh_hashana",
    "currently_rosh_hashana",
    "second_day_rosh_hashana_night",
    "second_day_rosh_hashana_day",
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
    MELACHA_PARAMS,
    ids=MELACHA_TEST_IDS,
)
async def test_issur_melacha_sensor(
    hass,
    legacy_patchable_time,
    now,
    candle_lighting,
    havdalah,
    diaspora,
    tzname,
    latitude,
    longitude,
    result,
):
    """Test Issur Melacha sensor output."""
    time_zone = dt_util.get_time_zone(tzname)
    test_time = time_zone.localize(now)

    hass.config.time_zone = time_zone
    hass.config.latitude = latitude
    hass.config.longitude = longitude

    registry = await hass.helpers.entity_registry.async_get_registry()

    with alter_time(test_time), patch(
        "homeassistant.helpers.event.async_track_point_in_time"
    ) as async_track_point_in_time:
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

        assert (
            hass.states.get("binary_sensor.test_issur_melacha_in_effect").state
            == result["state"]
        )
        entity = registry.async_get("binary_sensor.test_issur_melacha_in_effect")
        target_uid = "_".join(
            map(
                str,
                [
                    latitude,
                    longitude,
                    time_zone,
                    HDATE_DEFAULT_ALTITUDE,
                    diaspora,
                    "english",
                    candle_lighting,
                    havdalah,
                    "issur_melacha_in_effect",
                ],
            )
        )
        assert entity.unique_id == target_uid

        assert async_track_point_in_time.call_args[0][2] == result["update"]


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
    [
        make_nyc_test_params(dt(2020, 10, 23, 17, 46), [STATE_OFF, STATE_ON]),
        make_nyc_test_params(dt(2020, 10, 24, 18, 44), [STATE_ON, STATE_OFF]),
    ],
    ids=["before_candle_lighting", "before_havdalah"],
)
async def test_issur_melacha_sensor_update(
    hass,
    legacy_patchable_time,
    now,
    candle_lighting,
    havdalah,
    diaspora,
    tzname,
    latitude,
    longitude,
    result,
):
    """Test Issur Melacha sensor output."""
    time_zone = dt_util.get_time_zone(tzname)
    test_time = time_zone.localize(now)

    hass.config.time_zone = time_zone
    hass.config.latitude = latitude
    hass.config.longitude = longitude

    with alter_time(test_time):
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

        assert (
            hass.states.get("binary_sensor.test_issur_melacha_in_effect").state
            == result[0]
        )

    test_time += timedelta(seconds=61)
    with alter_time(test_time):
        async_fire_time_changed(hass, test_time)
        await hass.async_block_till_done()

        assert (
            hass.states.get("binary_sensor.test_issur_melacha_in_effect").state
            == result[1]
        )
