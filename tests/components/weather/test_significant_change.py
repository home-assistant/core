"""Test the Weather significant change platform."""

import pytest

from homeassistant.components.weather import (
    WeatherEntityCapabilityAttribute,
    WeatherEntityStateAttribute,
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
            {WeatherEntityCapabilityAttribute.PRECIPITATION_UNIT: "a"},
            {WeatherEntityCapabilityAttribute.PRECIPITATION_UNIT: "b"},
            False,
        ),
        (
            {WeatherEntityCapabilityAttribute.PRESSURE_UNIT: "a"},
            {WeatherEntityCapabilityAttribute.PRESSURE_UNIT: "b"},
            False,
        ),
        (
            {WeatherEntityCapabilityAttribute.TEMPERATURE_UNIT: "a"},
            {WeatherEntityCapabilityAttribute.TEMPERATURE_UNIT: "b"},
            False,
        ),
        (
            {WeatherEntityCapabilityAttribute.VISIBILITY_UNIT: "a"},
            {WeatherEntityCapabilityAttribute.VISIBILITY_UNIT: "b"},
            False,
        ),
        (
            {WeatherEntityCapabilityAttribute.WIND_SPEED_UNIT: "a"},
            {WeatherEntityCapabilityAttribute.WIND_SPEED_UNIT: "b"},
            False,
        ),
        (
            {
                WeatherEntityCapabilityAttribute.PRECIPITATION_UNIT: "a",
                WeatherEntityCapabilityAttribute.WIND_SPEED_UNIT: "a",
            },
            {
                WeatherEntityCapabilityAttribute.PRECIPITATION_UNIT: "b",
                WeatherEntityCapabilityAttribute.WIND_SPEED_UNIT: "a",
            },
            False,
        ),
        # significant attributes, close to but not significant change
        (
            {WeatherEntityStateAttribute.APPARENT_TEMPERATURE: 20},
            {WeatherEntityStateAttribute.APPARENT_TEMPERATURE: 20.4},
            False,
        ),
        (
            {WeatherEntityStateAttribute.APPARENT_TEMPERATURE: 68},
            {
                WeatherEntityStateAttribute.APPARENT_TEMPERATURE: 68.9,
                WeatherEntityCapabilityAttribute.TEMPERATURE_UNIT: UnitOfTemperature.FAHRENHEIT,
            },
            False,
        ),
        (
            {WeatherEntityStateAttribute.DEW_POINT: 20},
            {WeatherEntityStateAttribute.DEW_POINT: 20.4},
            False,
        ),
        (
            {WeatherEntityStateAttribute.TEMPERATURE: 20},
            {WeatherEntityStateAttribute.TEMPERATURE: 20.4},
            False,
        ),
        (
            {WeatherEntityStateAttribute.CLOUD_COVERAGE: 80},
            {WeatherEntityStateAttribute.CLOUD_COVERAGE: 80.9},
            False,
        ),
        (
            {WeatherEntityStateAttribute.HUMIDITY: 90},
            {WeatherEntityStateAttribute.HUMIDITY: 89.1},
            False,
        ),
        (
            {WeatherEntityStateAttribute.WIND_BEARING: "W"},  # W = 270°
            {WeatherEntityStateAttribute.WIND_BEARING: 269.1},
            False,
        ),
        (
            {WeatherEntityStateAttribute.WIND_BEARING: "W"},
            {WeatherEntityStateAttribute.WIND_BEARING: "W"},
            False,
        ),
        (
            {WeatherEntityStateAttribute.WIND_BEARING: 270},
            {WeatherEntityStateAttribute.WIND_BEARING: 269.1},
            False,
        ),
        (
            {WeatherEntityStateAttribute.WIND_GUST_SPEED: 5},
            {
                WeatherEntityStateAttribute.WIND_GUST_SPEED: 5.9,
                WeatherEntityCapabilityAttribute.WIND_SPEED_UNIT: UnitOfSpeed.KILOMETERS_PER_HOUR,
            },
            False,
        ),
        (
            {WeatherEntityStateAttribute.WIND_GUST_SPEED: 5},
            {
                WeatherEntityStateAttribute.WIND_GUST_SPEED: 5.4,
                WeatherEntityCapabilityAttribute.WIND_SPEED_UNIT: UnitOfSpeed.METERS_PER_SECOND,
            },
            False,
        ),
        (
            {WeatherEntityStateAttribute.WIND_SPEED: 5},
            {
                WeatherEntityStateAttribute.WIND_SPEED: 5.9,
                WeatherEntityCapabilityAttribute.WIND_SPEED_UNIT: UnitOfSpeed.KILOMETERS_PER_HOUR,
            },
            False,
        ),
        (
            {WeatherEntityStateAttribute.WIND_SPEED: 5},
            {
                WeatherEntityStateAttribute.WIND_SPEED: 5.4,
                WeatherEntityCapabilityAttribute.WIND_SPEED_UNIT: UnitOfSpeed.METERS_PER_SECOND,
            },
            False,
        ),
        (
            {WeatherEntityStateAttribute.UV_INDEX: 1},
            {WeatherEntityStateAttribute.UV_INDEX: 1.09},
            False,
        ),
        (
            {WeatherEntityStateAttribute.OZONE: 20},
            {WeatherEntityStateAttribute.OZONE: 20.9},
            False,
        ),
        (
            {WeatherEntityStateAttribute.PRESSURE: 1000},
            {WeatherEntityStateAttribute.PRESSURE: 1000.9},
            False,
        ),
        (
            {WeatherEntityStateAttribute.PRESSURE: 750.06},
            {
                WeatherEntityStateAttribute.PRESSURE: 750.74,
                WeatherEntityCapabilityAttribute.PRESSURE_UNIT: UnitOfPressure.MMHG,
            },
            False,
        ),
        (
            {WeatherEntityStateAttribute.PRESSURE: 100},
            {
                WeatherEntityStateAttribute.PRESSURE: 100.09,
                WeatherEntityCapabilityAttribute.PRESSURE_UNIT: UnitOfPressure.KPA,
            },
            False,
        ),
        (
            {WeatherEntityStateAttribute.PRESSURE: 29.5},
            {
                WeatherEntityStateAttribute.PRESSURE: 29.54,
                WeatherEntityCapabilityAttribute.PRESSURE_UNIT: UnitOfPressure.INHG,
            },
            False,
        ),
        # significant attributes with significant change
        (
            {WeatherEntityStateAttribute.APPARENT_TEMPERATURE: 20},
            {WeatherEntityStateAttribute.APPARENT_TEMPERATURE: 20.5},
            True,
        ),
        (
            {WeatherEntityStateAttribute.APPARENT_TEMPERATURE: 68},
            {
                WeatherEntityStateAttribute.APPARENT_TEMPERATURE: 69,
                WeatherEntityCapabilityAttribute.TEMPERATURE_UNIT: UnitOfTemperature.FAHRENHEIT,
            },
            True,
        ),
        (
            {WeatherEntityStateAttribute.DEW_POINT: 20},
            {WeatherEntityStateAttribute.DEW_POINT: 20.5},
            True,
        ),
        (
            {WeatherEntityStateAttribute.TEMPERATURE: 20},
            {WeatherEntityStateAttribute.TEMPERATURE: 20.5},
            True,
        ),
        (
            {WeatherEntityStateAttribute.CLOUD_COVERAGE: 80},
            {WeatherEntityStateAttribute.CLOUD_COVERAGE: 81},
            True,
        ),
        (
            {WeatherEntityStateAttribute.HUMIDITY: 90},
            {WeatherEntityStateAttribute.HUMIDITY: 89},
            True,
        ),
        (
            {WeatherEntityStateAttribute.WIND_BEARING: "W"},  # W = 270°
            {WeatherEntityStateAttribute.WIND_BEARING: 269},
            True,
        ),
        (
            {WeatherEntityStateAttribute.WIND_BEARING: "W"},
            {WeatherEntityStateAttribute.WIND_BEARING: "NW"},  # NW = 315°
            True,
        ),
        (
            {WeatherEntityStateAttribute.WIND_BEARING: 270},
            {WeatherEntityStateAttribute.WIND_BEARING: 269},
            True,
        ),
        (
            {WeatherEntityStateAttribute.WIND_GUST_SPEED: 5},
            {
                WeatherEntityStateAttribute.WIND_GUST_SPEED: 6,
                WeatherEntityCapabilityAttribute.WIND_SPEED_UNIT: UnitOfSpeed.KILOMETERS_PER_HOUR,
            },
            True,
        ),
        (
            {WeatherEntityStateAttribute.WIND_GUST_SPEED: 5},
            {
                WeatherEntityStateAttribute.WIND_GUST_SPEED: 5.5,
                WeatherEntityCapabilityAttribute.WIND_SPEED_UNIT: UnitOfSpeed.METERS_PER_SECOND,
            },
            True,
        ),
        (
            {WeatherEntityStateAttribute.WIND_SPEED: 5},
            {
                WeatherEntityStateAttribute.WIND_SPEED: 6,
                WeatherEntityCapabilityAttribute.WIND_SPEED_UNIT: UnitOfSpeed.KILOMETERS_PER_HOUR,
            },
            True,
        ),
        (
            {WeatherEntityStateAttribute.WIND_SPEED: 5},
            {
                WeatherEntityStateAttribute.WIND_SPEED: 5.5,
                WeatherEntityCapabilityAttribute.WIND_SPEED_UNIT: UnitOfSpeed.METERS_PER_SECOND,
            },
            True,
        ),
        (
            {WeatherEntityStateAttribute.UV_INDEX: 1},
            {WeatherEntityStateAttribute.UV_INDEX: 1.1},
            True,
        ),
        (
            {WeatherEntityStateAttribute.OZONE: 20},
            {WeatherEntityStateAttribute.OZONE: 21},
            True,
        ),
        (
            {WeatherEntityStateAttribute.PRESSURE: 1000},
            {WeatherEntityStateAttribute.PRESSURE: 1001},
            True,
        ),
        (
            {WeatherEntityStateAttribute.PRESSURE: 750},
            {
                WeatherEntityStateAttribute.PRESSURE: 749,
                WeatherEntityCapabilityAttribute.PRESSURE_UNIT: UnitOfPressure.MMHG,
            },
            True,
        ),
        (
            {WeatherEntityStateAttribute.PRESSURE: 100},
            {
                WeatherEntityStateAttribute.PRESSURE: 100.11,
                WeatherEntityCapabilityAttribute.PRESSURE_UNIT: UnitOfPressure.KPA,
            },
            True,
        ),
        (
            {WeatherEntityStateAttribute.PRESSURE: 29.5},
            {
                WeatherEntityStateAttribute.PRESSURE: 29.55,
                WeatherEntityCapabilityAttribute.PRESSURE_UNIT: UnitOfPressure.INHG,
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
            {WeatherEntityStateAttribute.APPARENT_TEMPERATURE: 30},
            {WeatherEntityStateAttribute.APPARENT_TEMPERATURE: "invalid"},
            False,
        ),
        (
            {WeatherEntityStateAttribute.APPARENT_TEMPERATURE: 30},
            {WeatherEntityStateAttribute.APPARENT_TEMPERATURE: None},
            False,
        ),
        (
            {WeatherEntityStateAttribute.WIND_BEARING: "NNW"},
            {WeatherEntityStateAttribute.WIND_BEARING: "invalid"},
            False,
        ),
        # invalid old values
        (
            {WeatherEntityStateAttribute.APPARENT_TEMPERATURE: "invalid"},
            {WeatherEntityStateAttribute.APPARENT_TEMPERATURE: 30},
            True,
        ),
        (
            {WeatherEntityStateAttribute.APPARENT_TEMPERATURE: None},
            {WeatherEntityStateAttribute.APPARENT_TEMPERATURE: 30},
            True,
        ),
        (
            {WeatherEntityStateAttribute.WIND_BEARING: "invalid"},
            {WeatherEntityStateAttribute.WIND_BEARING: "NNW"},
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
