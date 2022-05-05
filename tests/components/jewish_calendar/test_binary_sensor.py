"""The tests for the Jewish calendar binary sensors."""
from datetime import datetime as dt, timedelta

import pytest

from homeassistant.components import jewish_calendar
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from . import (
    HDATE_DEFAULT_ALTITUDE,
    alter_time,
    make_jerusalem_test_params,
    make_nyc_test_params,
)

from tests.common import async_fire_time_changed

MELACHA_PARAMS = [
    make_nyc_test_params(
        dt(2018, 9, 1, 16, 0),
        {
            "state": STATE_ON,
            "update": dt(2018, 9, 1, 20, 14),
            "new_state": STATE_OFF,
        },
    ),
    make_nyc_test_params(
        dt(2018, 9, 1, 20, 21),
        {
            "state": STATE_OFF,
            "update": dt(2018, 9, 2, 6, 21),
            "new_state": STATE_OFF,
        },
    ),
    make_nyc_test_params(
        dt(2018, 9, 7, 13, 1),
        {
            "state": STATE_OFF,
            "update": dt(2018, 9, 7, 19, 4),
            "new_state": STATE_ON,
        },
    ),
    make_nyc_test_params(
        dt(2018, 9, 8, 21, 25),
        {
            "state": STATE_OFF,
            "update": dt(2018, 9, 9, 6, 27),
            "new_state": STATE_OFF,
        },
    ),
    make_nyc_test_params(
        dt(2018, 9, 9, 21, 25),
        {
            "state": STATE_ON,
            "update": dt(2018, 9, 10, 6, 28),
            "new_state": STATE_ON,
        },
    ),
    make_nyc_test_params(
        dt(2018, 9, 10, 21, 25),
        {
            "state": STATE_ON,
            "update": dt(2018, 9, 11, 6, 29),
            "new_state": STATE_ON,
        },
    ),
    make_nyc_test_params(
        dt(2018, 9, 11, 11, 25),
        {
            "state": STATE_ON,
            "update": dt(2018, 9, 11, 19, 57),
            "new_state": STATE_OFF,
        },
    ),
    make_nyc_test_params(
        dt(2018, 9, 29, 16, 25),
        {
            "state": STATE_ON,
            "update": dt(2018, 9, 29, 19, 25),
            "new_state": STATE_OFF,
        },
    ),
    make_nyc_test_params(
        dt(2018, 9, 29, 21, 25),
        {
            "state": STATE_OFF,
            "update": dt(2018, 9, 30, 6, 48),
            "new_state": STATE_OFF,
        },
    ),
    make_nyc_test_params(
        dt(2018, 9, 30, 21, 25),
        {
            "state": STATE_ON,
            "update": dt(2018, 10, 1, 6, 49),
            "new_state": STATE_ON,
        },
    ),
    make_nyc_test_params(
        dt(2018, 10, 1, 21, 25),
        {
            "state": STATE_ON,
            "update": dt(2018, 10, 2, 6, 50),
            "new_state": STATE_ON,
        },
    ),
    make_jerusalem_test_params(
        dt(2018, 9, 29, 21, 25),
        {
            "state": STATE_OFF,
            "update": dt(2018, 9, 30, 6, 29),
            "new_state": STATE_OFF,
        },
    ),
    make_jerusalem_test_params(
        dt(2018, 10, 1, 11, 25),
        {
            "state": STATE_ON,
            "update": dt(2018, 10, 1, 19, 2),
            "new_state": STATE_OFF,
        },
    ),
    make_jerusalem_test_params(
        dt(2018, 10, 1, 21, 25),
        {
            "state": STATE_OFF,
            "update": dt(2018, 10, 2, 6, 31),
            "new_state": STATE_OFF,
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
    test_time = now.replace(tzinfo=time_zone)

    hass.config.set_time_zone(tzname)
    hass.config.latitude = latitude
    hass.config.longitude = longitude

    registry = er.async_get(hass)

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
            == result["state"]
        )
        entity = registry.async_get("binary_sensor.test_issur_melacha_in_effect")
        target_uid = "_".join(
            map(
                str,
                [
                    latitude,
                    longitude,
                    tzname,
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

        with alter_time(result["update"]):
            async_fire_time_changed(hass, result["update"])
            await hass.async_block_till_done()
            assert (
                hass.states.get("binary_sensor.test_issur_melacha_in_effect").state
                == result["new_state"]
            )


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
        make_nyc_test_params(
            dt(2020, 10, 23, 17, 44, 59, 999999), [STATE_OFF, STATE_ON]
        ),
        make_nyc_test_params(
            dt(2020, 10, 24, 18, 42, 59, 999999), [STATE_ON, STATE_OFF]
        ),
    ],
    ids=["before_candle_lighting", "before_havdalah"],
)
async def test_issur_melacha_sensor_update(
    hass,
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
    test_time = now.replace(tzinfo=time_zone)

    hass.config.set_time_zone(tzname)
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

    test_time += timedelta(microseconds=1)
    with alter_time(test_time):
        async_fire_time_changed(hass, test_time)
        await hass.async_block_till_done()
        assert (
            hass.states.get("binary_sensor.test_issur_melacha_in_effect").state
            == result[1]
        )


async def test_no_discovery_info(hass, caplog):
    """Test setup without discovery info."""
    assert BINARY_SENSOR_DOMAIN not in hass.config.components
    assert await async_setup_component(
        hass,
        BINARY_SENSOR_DOMAIN,
        {BINARY_SENSOR_DOMAIN: {"platform": jewish_calendar.DOMAIN}},
    )
    await hass.async_block_till_done()
    assert BINARY_SENSOR_DOMAIN in hass.config.components
