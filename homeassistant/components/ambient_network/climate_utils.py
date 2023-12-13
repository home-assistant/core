"""Climate utility functions for the Ambient Weather Network integration."""
from __future__ import annotations

from math import log, sqrt
from typing import cast

from homeassistant.const import UnitOfSpeed, UnitOfTemperature
from homeassistant.util.unit_conversion import SpeedConverter, TemperatureConverter

MAGNUS_A = 17.27
MAGNUS_B = 237.7


class ClimateUtils:
    """Climate utility functions."""

    @staticmethod
    def dew_point_celsius(temp_celsius: float, humidity: float) -> float:
        """Calculate the dew point in Celsius."""

        g = MAGNUS_A * temp_celsius / (MAGNUS_B + temp_celsius) + log(humidity / 100.0)
        return MAGNUS_B * g / (MAGNUS_A - g)

    @staticmethod
    def dew_point_fahrenheit(
        temp_fahrenheit: float | None, humidity: float | None
    ) -> float | None:
        """Calculate the dew point in Fahrenheit."""

        if temp_fahrenheit is None or humidity is None:
            return None
        humidity = min(humidity, 100)
        return TemperatureConverter.convert(
            ClimateUtils.dew_point_celsius(
                TemperatureConverter.convert(
                    temp_fahrenheit,
                    UnitOfTemperature.FAHRENHEIT,
                    UnitOfTemperature.CELSIUS,
                ),
                humidity,
            ),
            UnitOfTemperature.CELSIUS,
            UnitOfTemperature.FAHRENHEIT,
        )

    @staticmethod
    def _wind_chill_fahrenheit(temp_fahrenheit: float, wind_speed_mph: float) -> float:
        """Calculate the wind chill temperature in Fahrenheit."""

        return cast(
            float,
            35.74
            + 0.6215 * temp_fahrenheit
            - 35.75 * wind_speed_mph**0.16
            + 0.4275 * temp_fahrenheit * wind_speed_mph**0.16,
        )

    @staticmethod
    def _heat_index_fahrenheit(temp_fahrenheit: float, humidity: float) -> float:
        """Calculate the heat index temperature in Fahrenheit."""

        result = 0.5 * (
            temp_fahrenheit + 61 + (temp_fahrenheit - 68) * 1.2 + humidity * 0.094
        )
        if temp_fahrenheit >= 80:
            heat_index_base = (
                -42.379
                + 2.04901523 * temp_fahrenheit
                + 10.14333127 * humidity
                + -0.22475541 * temp_fahrenheit * humidity
                + -0.00683783 * temp_fahrenheit * temp_fahrenheit
                + -0.05481717 * humidity * humidity
                + 0.00122874 * temp_fahrenheit * temp_fahrenheit * humidity
                + 0.00085282 * temp_fahrenheit * humidity * humidity
                + -0.00000199 * temp_fahrenheit * temp_fahrenheit * humidity * humidity
            )
            if humidity < 13 and temp_fahrenheit <= 112:
                result = heat_index_base - (13 - humidity) / 4 * sqrt(
                    (17 - (abs(temp_fahrenheit - 95))) / 17
                )
            elif humidity > 85 and temp_fahrenheit <= 87:
                result = heat_index_base + (humidity - 85) / 10 * (
                    (87 - temp_fahrenheit) / 5
                )
            else:
                result = heat_index_base
        return result

    @staticmethod
    def feels_like_fahrenheit(
        temp_fahrenheit: float | None,
        humidity: float | None,
        wind_speed_mph: float | None,
    ) -> float | None:
        """Calculate the feels like temperature in Fahrenheit."""

        if temp_fahrenheit is None or humidity is None or wind_speed_mph is None:
            return None
        if temp_fahrenheit < 50 and wind_speed_mph > 3:
            return ClimateUtils._wind_chill_fahrenheit(temp_fahrenheit, wind_speed_mph)
        if temp_fahrenheit > 68:
            return ClimateUtils._heat_index_fahrenheit(temp_fahrenheit, humidity)
        return temp_fahrenheit

    @staticmethod
    def feels_like_celsius(
        temp_celsius: float | None, humidity: float | None, wind_speed_kph: float | None
    ) -> float | None:
        """Calculate the feels like temperature in Celsius."""

        if temp_celsius is None or humidity is None or wind_speed_kph is None:
            return None

        temp_fahrenheit = TemperatureConverter.convert(
            temp_celsius, UnitOfTemperature.CELSIUS, UnitOfTemperature.FAHRENHEIT
        )
        wind_speed_mph = SpeedConverter.convert(
            wind_speed_kph,
            UnitOfSpeed.KILOMETERS_PER_HOUR,
            UnitOfSpeed.MILES_PER_HOUR,
        )
        return TemperatureConverter.convert(
            # Result cannot be None, so cast it to float to avoid the mypy error.
            cast(
                float,
                ClimateUtils.feels_like_fahrenheit(
                    temp_fahrenheit, humidity, wind_speed_mph
                ),
            ),
            UnitOfTemperature.FAHRENHEIT,
            UnitOfTemperature.CELSIUS,
        )
