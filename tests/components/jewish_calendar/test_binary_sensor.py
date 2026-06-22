"""The tests for the Jewish calendar binary sensors."""

from collections.abc import AsyncGenerator
from datetime import datetime as dt
from typing import Any

import pytest

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from . import TimeValue, TimeValueSequence

# Test sequences for issur melacha (forbidden work) binary sensor
MELACHA_TEST_SEQUENCES = [
    # New York scenarios
    pytest.param(
        "New York",
        TimeValueSequence(
            [
                TimeValue(dt(2018, 9, 1, 16, 0), STATE_ON),
                TimeValue(dt(2018, 9, 1, 20, 14), STATE_OFF),
            ]
        ),
        id="currently_first_shabbat",
    ),
    pytest.param(
        "New York",
        TimeValueSequence(
            [
                TimeValue(dt(2018, 9, 1, 20, 21), STATE_OFF),
                TimeValue(dt(2018, 9, 2, 6, 21), STATE_OFF),
            ]
        ),
        id="after_first_shabbat",
    ),
    pytest.param(
        "New York",
        TimeValueSequence(
            [
                TimeValue(dt(2018, 9, 7, 13, 1), STATE_OFF),
                TimeValue(dt(2018, 9, 7, 19, 4), STATE_ON),
            ]
        ),
        id="friday_upcoming_shabbat",
    ),
    pytest.param(
        "New York",
        TimeValueSequence(
            [
                TimeValue(dt(2018, 9, 8, 21, 25), STATE_OFF),
                TimeValue(dt(2018, 9, 9, 6, 27), STATE_OFF),
            ]
        ),
        id="upcoming_rosh_hashana",
    ),
    pytest.param(
        "New York",
        TimeValueSequence(
            [
                TimeValue(dt(2018, 9, 9, 21, 25), STATE_ON),
                TimeValue(dt(2018, 9, 10, 6, 28), STATE_ON),
            ]
        ),
        id="currently_rosh_hashana",
    ),
    pytest.param(
        "New York",
        TimeValueSequence(
            [
                TimeValue(dt(2018, 9, 10, 21, 25), STATE_ON),
                TimeValue(dt(2018, 9, 11, 6, 29), STATE_ON),
            ]
        ),
        id="second_day_rosh_hashana_night",
    ),
    pytest.param(
        "New York",
        TimeValueSequence(
            [
                TimeValue(dt(2018, 9, 11, 11, 25), STATE_ON),
                TimeValue(dt(2018, 9, 11, 19, 57), STATE_OFF),
            ]
        ),
        id="second_day_rosh_hashana_day",
    ),
    pytest.param(
        "New York",
        TimeValueSequence(
            [
                TimeValue(dt(2018, 9, 29, 16, 25), STATE_ON),
                TimeValue(dt(2018, 9, 29, 19, 25), STATE_OFF),
            ]
        ),
        id="currently_shabbat_chol_hamoed",
    ),
    pytest.param(
        "New York",
        TimeValueSequence(
            [
                TimeValue(dt(2018, 9, 29, 21, 25), STATE_OFF),
                TimeValue(dt(2018, 9, 30, 6, 48), STATE_OFF),
            ]
        ),
        id="upcoming_two_day_yomtov_in_diaspora",
    ),
    pytest.param(
        "New York",
        TimeValueSequence(
            [
                TimeValue(dt(2018, 9, 30, 21, 25), STATE_ON),
                TimeValue(dt(2018, 10, 1, 6, 49), STATE_ON),
            ]
        ),
        id="currently_first_day_of_two_day_yomtov_in_diaspora",
    ),
    pytest.param(
        "New York",
        TimeValueSequence(
            [
                TimeValue(dt(2018, 10, 1, 21, 25), STATE_ON),
                TimeValue(dt(2018, 10, 2, 6, 50), STATE_ON),
            ]
        ),
        id="currently_second_day_of_two_day_yomtov_in_diaspora",
    ),
    # Jerusalem scenarios
    pytest.param(
        "Jerusalem",
        TimeValueSequence(
            [
                TimeValue(dt(2018, 9, 29, 21, 25), STATE_OFF),
                TimeValue(dt(2018, 9, 30, 6, 29), STATE_OFF),
            ]
        ),
        id="upcoming_one_day_yom_tov_in_israel",
    ),
    pytest.param(
        "Jerusalem",
        TimeValueSequence(
            [
                TimeValue(dt(2018, 10, 1, 11, 25), STATE_ON),
                TimeValue(dt(2018, 10, 1, 19, 2), STATE_OFF),
            ]
        ),
        id="currently_one_day_yom_tov_in_israel",
    ),
    pytest.param(
        "Jerusalem",
        TimeValueSequence(
            [
                TimeValue(dt(2018, 10, 1, 21, 25), STATE_OFF),
                TimeValue(dt(2018, 10, 2, 6, 31), STATE_OFF),
            ]
        ),
        id="after_one_day_yom_tov_in_israel",
    ),
]


@pytest.mark.parametrize(
    ("location_data", "test_sequence"), MELACHA_TEST_SEQUENCES, indirect=True
)
async def test_issur_melacha_sensor(
    hass: HomeAssistant, test_sequence: AsyncGenerator[Any]
) -> None:
    """Test Issur Melacha sensor output."""
    sensor_id = "binary_sensor.jewish_calendar_issur_melacha_in_effect"
    async for expected_state in test_sequence():
        current_state = hass.states.get(sensor_id).state
        assert current_state == expected_state


@pytest.mark.parametrize(
    ("location_data", "test_sequence"),
    [
        pytest.param(
            "New York",
            TimeValueSequence(
                [
                    TimeValue(dt(2020, 10, 23, 17, 44, 59, 999999), STATE_OFF),
                    TimeValue(dt(2020, 10, 23, 17, 45, 0), STATE_ON),
                    TimeValue(dt(2020, 10, 24, 18, 42, 59), STATE_ON),
                    TimeValue(dt(2020, 10, 24, 18, 43, 0), STATE_OFF),
                ]
            ),
            id="full_shabbat_cycle",
        ),
        pytest.param(
            "New York",
            TimeValueSequence(
                [
                    TimeValue(dt(2020, 10, 24, 18, 42, 59, 999999), STATE_ON),
                    TimeValue(dt(2020, 10, 24, 18, 43, 0), STATE_OFF),
                ]
            ),
            id="havdalah_transition",
        ),
    ],
    indirect=True,
)
async def test_issur_melacha_sensor_transitions(
    hass: HomeAssistant, test_sequence: AsyncGenerator[Any]
) -> None:
    """Test Issur Melacha sensor transitions at key times."""
    sensor_id = "binary_sensor.jewish_calendar_issur_melacha_in_effect"
    async for expected_state in test_sequence():
        current_state = hass.states.get(sensor_id).state
        assert current_state == expected_state
