"""Test the Weather significant change platform."""

import pytest

from homeassistant.components.weather.const import (
    ATTR_WEATHER_APPARENT_TEMPERATURE,
    ATTR_WEATHER_CLOUD_COVERAGE,
    ATTR_WEATHER_DEW_POINT,
    ATTR_WEATHER_HUMIDITY,
    ATTR_WEATHER_OZONE,
    ATTR_WEATHER_PRECIPITATION_UNIT,
    ATTR_WEATHER_PRESSURE,
    ATTR_WEATHER_PRESSURE_UNIT,
    ATTR_WEATHER_TEMPERATURE,
    ATTR_WEATHER_TEMPERATURE_UNIT,
    ATTR_WEATHER_UV_INDEX,
    ATTR_WEATHER_VISIBILITY_UNIT,
    ATTR_WEATHER_WIND_BEARING,
    ATTR_WEATHER_WIND_GUST_SPEED,
    ATTR_WEATHER_WIND_SPEED,
    ATTR_WEATHER_WIND_SPEED_UNIT,
)
from homeassistant.components.weather.significant_change import (
    async_check_significant_change,
)
from homeassistant.const import UnitOfPressure, UnitOfSpeed, UnitOfTemperature


async def test_significant_state_change() -> None:
    """Detect Weather significant state changes."""
    assert not async_check_significant_change(
        None, "clear-night", {}, "clear-night", {}
    )
    assert async_check_significant_change(None, "clear-night", {}, "cloudy", {})


@pytest.mark.parametrize(
    ("old_attrs", "new_attrs", "expected_result"),
    [
        # insignificant attributes
        (
            {ATTR_WEATHER_PRECIPITATION_UNIT: "a"},
            {ATTR_WEATHER_PRECIPITATION_UNIT: "b"},
            False,
        ),
        ({ATTR_WEATHER_PRESSURE_UNIT: "a"}, {ATTR_WEATHER_PRESSURE_UNIT: "b"}, False),
        (
            {ATTR_WEATHER_TEMPERATURE_UNIT: "a"},
            {ATTR_WEATHER_TEMPERATURE_UNIT: "b"},
            False,
        ),
        (
            {ATTR_WEATHER_VISIBILITY_UNIT: "a"},
            {ATTR_WEATHER_VISIBILITY_UNIT: "b"},
            False,
        ),
        (
            {ATTR_WEATHER_WIND_SPEED_UNIT: "a"},
            {ATTR_WEATHER_WIND_SPEED_UNIT: "b"},
            False,
        ),
        (
            {ATTR_WEATHER_PRECIPITATION_UNIT: "a", ATTR_WEATHER_WIND_SPEED_UNIT: "a"},
            {ATTR_WEATHER_PRECIPITATION_UNIT: "b", ATTR_WEATHER_WIND_SPEED_UNIT: "a"},
            False,
        ),
        # significant attributes, close to but not significant change
        (
            {ATTR_WEATHER_APPARENT_TEMPERATURE: 20},
            {ATTR_WEATHER_APPARENT_TEMPERATURE: 20.4},
            False,
        ),
        (
            {ATTR_WEATHER_APPARENT_TEMPERATURE: 68},
            {
                ATTR_WEATHER_APPARENT_TEMPERATURE: 68.9,
                ATTR_WEATHER_TEMPERATURE_UNIT: UnitOfTemperature.FAHRENHEIT,
            },
            False,
        ),
        (
            {ATTR_WEATHER_DEW_POINT: 20},
            {ATTR_WEATHER_DEW_POINT: 20.4},
            False,
        ),
        (
            {ATTR_WEATHER_TEMPERATURE: 20},
            {ATTR_WEATHER_TEMPERATURE: 20.4},
            False,
        ),
        (
            {ATTR_WEATHER_CLOUD_COVERAGE: 80},
            {ATTR_WEATHER_CLOUD_COVERAGE: 80.9},
            False,
        ),
        (
            {ATTR_WEATHER_HUMIDITY: 90},
            {ATTR_WEATHER_HUMIDITY: 89.1},
            False,
        ),
        (
            {ATTR_WEATHER_WIND_BEARING: "W"},  # W = 270°
            {ATTR_WEATHER_WIND_BEARING: 269.1},
            False,
        ),
        (
            {ATTR_WEATHER_WIND_BEARING: "W"},
            {ATTR_WEATHER_WIND_BEARING: "W"},
            False,
        ),
        (
            {ATTR_WEATHER_WIND_BEARING: 270},
            {ATTR_WEATHER_WIND_BEARING: 269.1},
            False,
        ),
        (
            {ATTR_WEATHER_WIND_GUST_SPEED: 5},
            {
                ATTR_WEATHER_WIND_GUST_SPEED: 5.9,
                ATTR_WEATHER_WIND_SPEED_UNIT: UnitOfSpeed.KILOMETERS_PER_HOUR,
            },
            False,
        ),
        (
            {ATTR_WEATHER_WIND_GUST_SPEED: 5},
            {
                ATTR_WEATHER_WIND_GUST_SPEED: 5.4,
                ATTR_WEATHER_WIND_SPEED_UNIT: UnitOfSpeed.METERS_PER_SECOND,
            },
            False,
        ),
        (
            {ATTR_WEATHER_WIND_SPEED: 5},
            {
                ATTR_WEATHER_WIND_SPEED: 5.9,
                ATTR_WEATHER_WIND_SPEED_UNIT: UnitOfSpeed.KILOMETERS_PER_HOUR,
            },
            False,
        ),
        (
            {ATTR_WEATHER_WIND_SPEED: 5},
            {
                ATTR_WEATHER_WIND_SPEED: 5.4,
                ATTR_WEATHER_WIND_SPEED_UNIT: UnitOfSpeed.METERS_PER_SECOND,
            },
            False,
        ),
        (
            {ATTR_WEATHER_UV_INDEX: 1},
            {ATTR_WEATHER_UV_INDEX: 1.09},
            False,
        ),
        (
            {ATTR_WEATHER_OZONE: 20},
            {ATTR_WEATHER_OZONE: 20.9},
            False,
        ),
        (
            {ATTR_WEATHER_PRESSURE: 1000},
            {ATTR_WEATHER_PRESSURE: 1000.9},
            False,
        ),
        (
            {ATTR_WEATHER_PRESSURE: 750.06},
            {
                ATTR_WEATHER_PRESSURE: 750.74,
                ATTR_WEATHER_PRESSURE_UNIT: UnitOfPressure.MMHG,
            },
            False,
        ),
        (
            {ATTR_WEATHER_PRESSURE: 29.5},
            {
                ATTR_WEATHER_PRESSURE: 29.54,
                ATTR_WEATHER_PRESSURE_UNIT: UnitOfPressure.INHG,
            },
            False,
        ),
        # significant attributes with significant change
        (
            {ATTR_WEATHER_APPARENT_TEMPERATURE: 20},
            {ATTR_WEATHER_APPARENT_TEMPERATURE: 20.5},
            True,
        ),
        (
            {ATTR_WEATHER_APPARENT_TEMPERATURE: 68},
            {
                ATTR_WEATHER_APPARENT_TEMPERATURE: 69,
                ATTR_WEATHER_TEMPERATURE_UNIT: UnitOfTemperature.FAHRENHEIT,
            },
            True,
        ),
        (
            {ATTR_WEATHER_DEW_POINT: 20},
            {ATTR_WEATHER_DEW_POINT: 20.5},
            True,
        ),
        (
            {ATTR_WEATHER_TEMPERATURE: 20},
            {ATTR_WEATHER_TEMPERATURE: 20.5},
            True,
        ),
        (
            {ATTR_WEATHER_CLOUD_COVERAGE: 80},
            {ATTR_WEATHER_CLOUD_COVERAGE: 81},
            True,
        ),
        (
            {ATTR_WEATHER_HUMIDITY: 90},
            {ATTR_WEATHER_HUMIDITY: 89},
            True,
        ),
        (
            {ATTR_WEATHER_WIND_BEARING: "W"},  # W = 270°
            {ATTR_WEATHER_WIND_BEARING: 269},
            True,
        ),
        (
            {ATTR_WEATHER_WIND_BEARING: "W"},
            {ATTR_WEATHER_WIND_BEARING: "NW"},  # NW = 315°
            True,
        ),
        (
            {ATTR_WEATHER_WIND_BEARING: 270},
            {ATTR_WEATHER_WIND_BEARING: 269},
            True,
        ),
        (
            {ATTR_WEATHER_WIND_GUST_SPEED: 5},
            {
                ATTR_WEATHER_WIND_GUST_SPEED: 6,
                ATTR_WEATHER_WIND_SPEED_UNIT: UnitOfSpeed.KILOMETERS_PER_HOUR,
            },
            True,
        ),
        (
            {ATTR_WEATHER_WIND_GUST_SPEED: 5},
            {
                ATTR_WEATHER_WIND_GUST_SPEED: 5.5,
                ATTR_WEATHER_WIND_SPEED_UNIT: UnitOfSpeed.METERS_PER_SECOND,
            },
            True,
        ),
        (
            {ATTR_WEATHER_WIND_SPEED: 5},
            {
                ATTR_WEATHER_WIND_SPEED: 6,
                ATTR_WEATHER_WIND_SPEED_UNIT: UnitOfSpeed.KILOMETERS_PER_HOUR,
            },
            True,
        ),
        (
            {ATTR_WEATHER_WIND_SPEED: 5},
            {
                ATTR_WEATHER_WIND_SPEED: 5.5,
                ATTR_WEATHER_WIND_SPEED_UNIT: UnitOfSpeed.METERS_PER_SECOND,
            },
            True,
        ),
        (
            {ATTR_WEATHER_UV_INDEX: 1},
            {ATTR_WEATHER_UV_INDEX: 1.1},
            True,
        ),
        (
            {ATTR_WEATHER_OZONE: 20},
            {ATTR_WEATHER_OZONE: 21},
            True,
        ),
        (
            {ATTR_WEATHER_PRESSURE: 1000},
            {ATTR_WEATHER_PRESSURE: 1001},
            True,
        ),
        (
            {ATTR_WEATHER_PRESSURE: 750},
            {
                ATTR_WEATHER_PRESSURE: 749,
                ATTR_WEATHER_PRESSURE_UNIT: UnitOfPressure.MMHG,
            },
            True,
        ),
        (
            {ATTR_WEATHER_PRESSURE: 29.5},
            {
                ATTR_WEATHER_PRESSURE: 29.55,
                ATTR_WEATHER_PRESSURE_UNIT: UnitOfPressure.INHG,
            },
            True,
        ),
    ],
)
async def test_significant_atributes_change(
    old_attrs: dict, new_attrs: dict, expected_result: bool
) -> None:
    """Detect Weather significant attribute changes."""
    assert (
        async_check_significant_change(None, "state", old_attrs, "state", new_attrs)
        == expected_result
    )


@pytest.mark.parametrize(
    ("old_attrs", "new_attrs", "expected_result"),
    [
        # invalid new values
        (
            {ATTR_WEATHER_APPARENT_TEMPERATURE: 30},
            {ATTR_WEATHER_APPARENT_TEMPERATURE: "invalid"},
            False,
        ),
        (
            {ATTR_WEATHER_APPARENT_TEMPERATURE: 30},
            {ATTR_WEATHER_APPARENT_TEMPERATURE: None},
            False,
        ),
        (
            {ATTR_WEATHER_WIND_BEARING: "NNW"},
            {ATTR_WEATHER_WIND_BEARING: "invalid"},
            False,
        ),
        # invalid old values
        (
            {ATTR_WEATHER_APPARENT_TEMPERATURE: "invalid"},
            {ATTR_WEATHER_APPARENT_TEMPERATURE: 30},
            True,
        ),
        (
            {ATTR_WEATHER_APPARENT_TEMPERATURE: None},
            {ATTR_WEATHER_APPARENT_TEMPERATURE: 30},
            True,
        ),
        (
            {ATTR_WEATHER_WIND_BEARING: "invalid"},
            {ATTR_WEATHER_WIND_BEARING: "NNW"},
            True,
        ),
    ],
)
async def test_invalid_atributes_change(
    old_attrs: dict, new_attrs: dict, expected_result: bool
) -> None:
    """Detect Weather invalid attribute changes."""
    assert (
        async_check_significant_change(None, "state", old_attrs, "state", new_attrs)
        == expected_result
    )
