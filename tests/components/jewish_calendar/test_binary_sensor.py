"""The tests for the Jewish calendar binary sensors."""

from datetime import datetime as dt, timedelta
import logging

import pytest

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.jewish_calendar.const import (
    CONF_CANDLE_LIGHT_MINUTES,
    CONF_DIASPORA,
    CONF_HAVDALAH_OFFSET_MINUTES,
    DEFAULT_NAME,
    DOMAIN,
)
from homeassistant.const import CONF_LANGUAGE, CONF_PLATFORM, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from . import alter_time, make_jerusalem_test_params, make_nyc_test_params

from tests.common import MockConfigEntry, async_fire_time_changed

_LOGGER = logging.getLogger(__name__)


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
    (
        "now",
        "candle_lighting",
        "havdalah",
        "diaspora",
        "tzname",
        "latitude",
        "longitude",
        "result",
    ),
    MELACHA_PARAMS,
    ids=MELACHA_TEST_IDS,
)
async def test_issur_melacha_sensor(
    hass: HomeAssistant,
    now,
    candle_lighting,
    havdalah,
    diaspora,
    tzname,
    latitude,
    longitude,
    result,
) -> None:
    """Test Issur Melacha sensor output."""
    time_zone = dt_util.get_time_zone(tzname)
    test_time = now.replace(tzinfo=time_zone)

    await hass.config.async_set_time_zone(tzname)
    hass.config.latitude = latitude
    hass.config.longitude = longitude

    with alter_time(test_time):
        entry = MockConfigEntry(
            title=DEFAULT_NAME,
            domain=DOMAIN,
            data={
                CONF_LANGUAGE: "english",
                CONF_DIASPORA: diaspora,
                CONF_CANDLE_LIGHT_MINUTES: candle_lighting,
                CONF_HAVDALAH_OFFSET_MINUTES: havdalah,
            },
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert (
            hass.states.get(
                "binary_sensor.jewish_calendar_issur_melacha_in_effect"
            ).state
            == result["state"]
        )

        with alter_time(result["update"]):
            async_fire_time_changed(hass, result["update"])
            await hass.async_block_till_done()
            assert (
                hass.states.get(
                    "binary_sensor.jewish_calendar_issur_melacha_in_effect"
                ).state
                == result["new_state"]
            )


@pytest.mark.parametrize(
    (
        "now",
        "candle_lighting",
        "havdalah",
        "diaspora",
        "tzname",
        "latitude",
        "longitude",
        "result",
    ),
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
    hass: HomeAssistant,
    now,
    candle_lighting,
    havdalah,
    diaspora,
    tzname,
    latitude,
    longitude,
    result,
) -> None:
    """Test Issur Melacha sensor output."""
    time_zone = dt_util.get_time_zone(tzname)
    test_time = now.replace(tzinfo=time_zone)

    await hass.config.async_set_time_zone(tzname)
    hass.config.latitude = latitude
    hass.config.longitude = longitude

    with alter_time(test_time):
        entry = MockConfigEntry(
            title=DEFAULT_NAME,
            domain=DOMAIN,
            data={
                CONF_LANGUAGE: "english",
                CONF_DIASPORA: diaspora,
                CONF_CANDLE_LIGHT_MINUTES: candle_lighting,
                CONF_HAVDALAH_OFFSET_MINUTES: havdalah,
            },
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert (
            hass.states.get(
                "binary_sensor.jewish_calendar_issur_melacha_in_effect"
            ).state
            == result[0]
        )

    test_time += timedelta(microseconds=1)
    with alter_time(test_time):
        async_fire_time_changed(hass, test_time)
        await hass.async_block_till_done()
        assert (
            hass.states.get(
                "binary_sensor.jewish_calendar_issur_melacha_in_effect"
            ).state
            == result[1]
        )


async def test_no_discovery_info(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test setup without discovery info."""
    assert BINARY_SENSOR_DOMAIN not in hass.config.components
    assert await async_setup_component(
        hass,
        BINARY_SENSOR_DOMAIN,
        {BINARY_SENSOR_DOMAIN: {CONF_PLATFORM: DOMAIN}},
    )
    await hass.async_block_till_done()
    assert BINARY_SENSOR_DOMAIN in hass.config.components
