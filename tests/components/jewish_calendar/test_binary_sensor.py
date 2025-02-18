"""The tests for the Jewish calendar binary sensors."""

from datetime import datetime as dt, timedelta

from freezegun import freeze_time
import pytest

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.jewish_calendar.const import DOMAIN
from homeassistant.const import CONF_PLATFORM, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, async_fire_time_changed

MELACHA_PARAMS = [
    (
        "New York",
        dt(2018, 9, 1, 16, 0),
        {"state": STATE_ON, "update": dt(2018, 9, 1, 20, 14), "new_state": STATE_OFF},
    ),
    (
        "New York",
        dt(2018, 9, 1, 20, 21),
        {"state": STATE_OFF, "update": dt(2018, 9, 2, 6, 21), "new_state": STATE_OFF},
    ),
    (
        "New York",
        dt(2018, 9, 7, 13, 1),
        {"state": STATE_OFF, "update": dt(2018, 9, 7, 19, 4), "new_state": STATE_ON},
    ),
    (
        "New York",
        dt(2018, 9, 8, 21, 25),
        {"state": STATE_OFF, "update": dt(2018, 9, 9, 6, 27), "new_state": STATE_OFF},
    ),
    (
        "New York",
        dt(2018, 9, 9, 21, 25),
        {"state": STATE_ON, "update": dt(2018, 9, 10, 6, 28), "new_state": STATE_ON},
    ),
    (
        "New York",
        dt(2018, 9, 10, 21, 25),
        {"state": STATE_ON, "update": dt(2018, 9, 11, 6, 29), "new_state": STATE_ON},
    ),
    (
        "New York",
        dt(2018, 9, 11, 11, 25),
        {"state": STATE_ON, "update": dt(2018, 9, 11, 19, 57), "new_state": STATE_OFF},
    ),
    (
        "New York",
        dt(2018, 9, 29, 16, 25),
        {"state": STATE_ON, "update": dt(2018, 9, 29, 19, 25), "new_state": STATE_OFF},
    ),
    (
        "New York",
        dt(2018, 9, 29, 21, 25),
        {"state": STATE_OFF, "update": dt(2018, 9, 30, 6, 48), "new_state": STATE_OFF},
    ),
    (
        "New York",
        dt(2018, 9, 30, 21, 25),
        {"state": STATE_ON, "update": dt(2018, 10, 1, 6, 49), "new_state": STATE_ON},
    ),
    (
        "New York",
        dt(2018, 10, 1, 21, 25),
        {"state": STATE_ON, "update": dt(2018, 10, 2, 6, 50), "new_state": STATE_ON},
    ),
    (
        "Jerusalem",
        dt(2018, 9, 29, 21, 25),
        {"state": STATE_OFF, "update": dt(2018, 9, 30, 6, 29), "new_state": STATE_OFF},
    ),
    (
        "Jerusalem",
        dt(2018, 10, 1, 11, 25),
        {"state": STATE_ON, "update": dt(2018, 10, 1, 19, 2), "new_state": STATE_OFF},
    ),
    (
        "Jerusalem",
        dt(2018, 10, 1, 21, 25),
        {"state": STATE_OFF, "update": dt(2018, 10, 2, 6, 31), "new_state": STATE_OFF},
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
    "jcal_params", MELACHA_PARAMS, ids=MELACHA_TEST_IDS, indirect=True
)
async def test_issur_melacha_sensor(
    hass: HomeAssistant, jcal_params: dict, config_entry: MockConfigEntry
) -> None:
    """Test Issur Melacha sensor output."""
    with freeze_time(jcal_params["test_time"]):
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert (
            hass.states.get(
                "binary_sensor.jewish_calendar_issur_melacha_in_effect"
            ).state
            == (result := jcal_params["results"])["state"]
        )

        with freeze_time(result["update"]):
            async_fire_time_changed(hass, result["update"])
            await hass.async_block_till_done()
            assert (
                hass.states.get(
                    "binary_sensor.jewish_calendar_issur_melacha_in_effect"
                ).state
                == result["new_state"]
            )


@pytest.mark.parametrize(
    "jcal_params",
    [
        ("New York", dt(2020, 10, 23, 17, 44, 59, 999999), [STATE_OFF, STATE_ON]),
        ("New York", dt(2020, 10, 24, 18, 42, 59, 999999), [STATE_ON, STATE_OFF]),
    ],
    ids=["before_candle_lighting", "before_havdalah"],
    indirect=True,
)
async def test_issur_melacha_sensor_update(
    hass: HomeAssistant, jcal_params: dict, config_entry: MockConfigEntry
) -> None:
    """Test Issur Melacha sensor output."""
    with freeze_time(test_time := jcal_params["test_time"]):
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert (
            hass.states.get(
                "binary_sensor.jewish_calendar_issur_melacha_in_effect"
            ).state
            == jcal_params["results"][0]
        )

    test_time += timedelta(microseconds=1)
    with freeze_time(test_time):
        async_fire_time_changed(hass, test_time)
        await hass.async_block_till_done()
        assert (
            hass.states.get(
                "binary_sensor.jewish_calendar_issur_melacha_in_effect"
            ).state
            == jcal_params["results"][1]
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
