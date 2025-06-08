"""The tests for the Jewish calendar binary sensors."""

from datetime import datetime as dt, timedelta
from typing import Any

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.jewish_calendar.const import DOMAIN
from homeassistant.const import CONF_PLATFORM, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import async_fire_time_changed

MELACHA_PARAMS = [
    pytest.param(
        "New York",
        dt(2018, 9, 1, 16, 0),
        {"state": STATE_ON, "update": dt(2018, 9, 1, 20, 14), "new_state": STATE_OFF},
        id="currently_first_shabbat",
    ),
    pytest.param(
        "New York",
        dt(2018, 9, 1, 20, 21),
        {"state": STATE_OFF, "update": dt(2018, 9, 2, 6, 21), "new_state": STATE_OFF},
        id="after_first_shabbat",
    ),
    pytest.param(
        "New York",
        dt(2018, 9, 7, 13, 1),
        {"state": STATE_OFF, "update": dt(2018, 9, 7, 19, 4), "new_state": STATE_ON},
        id="friday_upcoming_shabbat",
    ),
    pytest.param(
        "New York",
        dt(2018, 9, 8, 21, 25),
        {"state": STATE_OFF, "update": dt(2018, 9, 9, 6, 27), "new_state": STATE_OFF},
        id="upcoming_rosh_hashana",
    ),
    pytest.param(
        "New York",
        dt(2018, 9, 9, 21, 25),
        {"state": STATE_ON, "update": dt(2018, 9, 10, 6, 28), "new_state": STATE_ON},
        id="currently_rosh_hashana",
    ),
    pytest.param(
        "New York",
        dt(2018, 9, 10, 21, 25),
        {"state": STATE_ON, "update": dt(2018, 9, 11, 6, 29), "new_state": STATE_ON},
        id="second_day_rosh_hashana_night",
    ),
    pytest.param(
        "New York",
        dt(2018, 9, 11, 11, 25),
        {"state": STATE_ON, "update": dt(2018, 9, 11, 19, 57), "new_state": STATE_OFF},
        id="second_day_rosh_hashana_day",
    ),
    pytest.param(
        "New York",
        dt(2018, 9, 29, 16, 25),
        {"state": STATE_ON, "update": dt(2018, 9, 29, 19, 25), "new_state": STATE_OFF},
        id="currently_shabbat_chol_hamoed",
    ),
    pytest.param(
        "New York",
        dt(2018, 9, 29, 21, 25),
        {"state": STATE_OFF, "update": dt(2018, 9, 30, 6, 48), "new_state": STATE_OFF},
        id="upcoming_two_day_yomtov_in_diaspora",
    ),
    pytest.param(
        "New York",
        dt(2018, 9, 30, 21, 25),
        {"state": STATE_ON, "update": dt(2018, 10, 1, 6, 49), "new_state": STATE_ON},
        id="currently_first_day_of_two_day_yomtov_in_diaspora",
    ),
    pytest.param(
        "New York",
        dt(2018, 10, 1, 21, 25),
        {"state": STATE_ON, "update": dt(2018, 10, 2, 6, 50), "new_state": STATE_ON},
        id="currently_second_day_of_two_day_yomtov_in_diaspora",
    ),
    pytest.param(
        "Jerusalem",
        dt(2018, 9, 29, 21, 25),
        {"state": STATE_OFF, "update": dt(2018, 9, 30, 6, 29), "new_state": STATE_OFF},
        id="upcoming_one_day_yom_tov_in_israel",
    ),
    pytest.param(
        "Jerusalem",
        dt(2018, 10, 1, 11, 25),
        {"state": STATE_ON, "update": dt(2018, 10, 1, 19, 2), "new_state": STATE_OFF},
        id="currently_one_day_yom_tov_in_israel",
    ),
    pytest.param(
        "Jerusalem",
        dt(2018, 10, 1, 21, 25),
        {"state": STATE_OFF, "update": dt(2018, 10, 2, 6, 31), "new_state": STATE_OFF},
        id="after_one_day_yom_tov_in_israel",
    ),
]


@pytest.mark.parametrize(
    ("location_data", "test_time", "results"), MELACHA_PARAMS, indirect=True
)
@pytest.mark.usefixtures("setup_at_time")
async def test_issur_melacha_sensor(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, results: dict[str, Any]
) -> None:
    """Test Issur Melacha sensor output."""
    sensor_id = "binary_sensor.jewish_calendar_issur_melacha_in_effect"
    assert hass.states.get(sensor_id).state == results["state"]

    freezer.move_to(results["update"])
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(sensor_id).state == results["new_state"]


@pytest.mark.parametrize(
    ("location_data", "test_time", "results"),
    [
        ("New York", dt(2020, 10, 23, 17, 44, 59, 999999), [STATE_OFF, STATE_ON]),
        ("New York", dt(2020, 10, 24, 18, 42, 59, 999999), [STATE_ON, STATE_OFF]),
    ],
    ids=["before_candle_lighting", "before_havdalah"],
    indirect=True,
)
@pytest.mark.usefixtures("setup_at_time")
async def test_issur_melacha_sensor_update(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, results: list[str]
) -> None:
    """Test Issur Melacha sensor output."""
    sensor_id = "binary_sensor.jewish_calendar_issur_melacha_in_effect"
    assert hass.states.get(sensor_id).state == results[0]

    freezer.tick(timedelta(microseconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(sensor_id).state == results[1]


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
