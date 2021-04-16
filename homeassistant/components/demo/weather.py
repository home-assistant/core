"""Demo platform that offers fake meteorological data."""
from datetime import timedelta

from homeassistant.components.weather import (
    ATTR_CONDITION_CLOUDY,
    ATTR_CONDITION_EXCEPTIONAL,
    ATTR_CONDITION_FOG,
    ATTR_CONDITION_HAIL,
    ATTR_CONDITION_LIGHTNING,
    ATTR_CONDITION_LIGHTNING_RAINY,
    ATTR_CONDITION_PARTLYCLOUDY,
    ATTR_CONDITION_POURING,
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SNOWY,
    ATTR_CONDITION_SNOWY_RAINY,
    ATTR_CONDITION_SUNNY,
    ATTR_CONDITION_WINDY,
    ATTR_CONDITION_WINDY_VARIANT,
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_PRECIPITATION,
    ATTR_FORECAST_PRECIPITATION_PROBABILITY,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TEMP_LOW,
    ATTR_FORECAST_TIME,
    WeatherEntity,
)
from homeassistant.const import TEMP_CELSIUS, TEMP_FAHRENHEIT
import homeassistant.util.dt as dt_util

CONDITION_CLASSES = {
    ATTR_CONDITION_CLOUDY: [],
    ATTR_CONDITION_FOG: [],
    ATTR_CONDITION_HAIL: [],
    ATTR_CONDITION_LIGHTNING: [],
    ATTR_CONDITION_LIGHTNING_RAINY: [],
    ATTR_CONDITION_PARTLYCLOUDY: [],
    ATTR_CONDITION_POURING: [],
    ATTR_CONDITION_RAINY: ["shower rain"],
    ATTR_CONDITION_SNOWY: [],
    ATTR_CONDITION_SNOWY_RAINY: [],
    ATTR_CONDITION_SUNNY: ["sunshine"],
    ATTR_CONDITION_WINDY: [],
    ATTR_CONDITION_WINDY_VARIANT: [],
    ATTR_CONDITION_EXCEPTIONAL: [],
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Demo config entry."""
    setup_platform(hass, {}, async_add_entities)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Demo weather."""
    add_entities(
        [
            DemoWeather(
                "South",
                "Sunshine",
                21.6414,
                92,
                1099,
                0.5,
                TEMP_CELSIUS,
                [
                    [ATTR_CONDITION_RAINY, 1, 22, 15, 60],
                    [ATTR_CONDITION_RAINY, 5, 19, 8, 30],
                    [ATTR_CONDITION_CLOUDY, 0, 15, 9, 10],
                    [ATTR_CONDITION_SUNNY, 0, 12, 6, 0],
                    [ATTR_CONDITION_PARTLYCLOUDY, 2, 14, 7, 20],
                    [ATTR_CONDITION_RAINY, 15, 18, 7, 0],
                    [ATTR_CONDITION_FOG, 0.2, 21, 12, 100],
                ],
            ),
            DemoWeather(
                "North",
                "Shower rain",
                -12,
                54,
                987,
                4.8,
                TEMP_FAHRENHEIT,
                [
                    [ATTR_CONDITION_SNOWY, 2, -10, -15, 60],
                    [ATTR_CONDITION_PARTLYCLOUDY, 1, -13, -14, 25],
                    [ATTR_CONDITION_SUNNY, 0, -18, -22, 70],
                    [ATTR_CONDITION_SUNNY, 0.1, -23, -23, 90],
                    [ATTR_CONDITION_SNOWY, 4, -19, -20, 40],
                    [ATTR_CONDITION_SUNNY, 0.3, -14, -19, 0],
                    [ATTR_CONDITION_SUNNY, 0, -9, -12, 0],
                ],
            ),
        ]
    )


class DemoWeather(WeatherEntity):
    """Representation of a weather condition."""

    def __init__(
        self,
        name,
        condition,
        temperature,
        humidity,
        pressure,
        wind_speed,
        temperature_unit,
        forecast,
    ):
        """Initialize the Demo weather."""
        self._name = name
        self._condition = condition
        self._temperature = temperature
        self._temperature_unit = temperature_unit
        self._humidity = humidity
        self._pressure = pressure
        self._wind_speed = wind_speed
        self._forecast = forecast

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"Demo Weather {self._name}"

    @property
    def should_poll(self):
        """No polling needed for a demo weather condition."""
        return False

    @property
    def temperature(self):
        """Return the temperature."""
        return self._temperature

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._temperature_unit

    @property
    def humidity(self):
        """Return the humidity."""
        return self._humidity

    @property
    def wind_speed(self):
        """Return the wind speed."""
        return self._wind_speed

    @property
    def pressure(self):
        """Return the pressure."""
        return self._pressure

    @property
    def condition(self):
        """Return the weather condition."""
        return [
            k for k, v in CONDITION_CLASSES.items() if self._condition.lower() in v
        ][0]

    @property
    def attribution(self):
        """Return the attribution."""
        return "Powered by Home Assistant"

    @property
    def forecast(self):
        """Return the forecast."""
        reftime = dt_util.now().replace(hour=16, minute=00)

        forecast_data = []
        for entry in self._forecast:
            data_dict = {
                ATTR_FORECAST_TIME: reftime.isoformat(),
                ATTR_FORECAST_CONDITION: entry[0],
                ATTR_FORECAST_PRECIPITATION: entry[1],
                ATTR_FORECAST_TEMP: entry[2],
                ATTR_FORECAST_TEMP_LOW: entry[3],
                ATTR_FORECAST_PRECIPITATION_PROBABILITY: entry[4],
            }
            reftime = reftime + timedelta(hours=4)
            forecast_data.append(data_dict)

        return forecast_data
