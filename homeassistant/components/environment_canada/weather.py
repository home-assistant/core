"""Support for Environment Canada (EC) weather service."""
from __future__ import annotations

import datetime

from homeassistant.components.weather import (
    ATTR_CONDITION_CLEAR_NIGHT,
    ATTR_CONDITION_CLOUDY,
    ATTR_CONDITION_EXCEPTIONAL,
    ATTR_CONDITION_FOG,
    ATTR_CONDITION_LIGHTNING_RAINY,
    ATTR_CONDITION_PARTLYCLOUDY,
    ATTR_CONDITION_POURING,
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SNOWY,
    ATTR_CONDITION_SNOWY_RAINY,
    ATTR_CONDITION_SUNNY,
    ATTR_CONDITION_WINDY,
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_PRECIPITATION_PROBABILITY,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TEMP_LOW,
    ATTR_FORECAST_TIME,
    WeatherEntity,
)
from homeassistant.const import (
    LENGTH_KILOMETERS,
    LENGTH_MILES,
    PRESSURE_HPA,
    PRESSURE_INHG,
    TEMP_CELSIUS,
)
from homeassistant.util import dt

from . import ECBaseEntity, convert
from .const import DOMAIN

# Icon codes from:
# https://dd.weather.gc.ca/citypage_weather/docs/forecast_conditions_icon_code_descriptions_e.csv
EC_ICON_TO_HA_CONDITION_MAP = {
    0: ATTR_CONDITION_SUNNY,
    1: ATTR_CONDITION_SUNNY,
    2: ATTR_CONDITION_PARTLYCLOUDY,
    3: ATTR_CONDITION_PARTLYCLOUDY,
    4: ATTR_CONDITION_PARTLYCLOUDY,
    5: ATTR_CONDITION_PARTLYCLOUDY,
    6: ATTR_CONDITION_RAINY,
    7: ATTR_CONDITION_SNOWY_RAINY,
    8: ATTR_CONDITION_SNOWY,
    9: ATTR_CONDITION_LIGHTNING_RAINY,
    10: ATTR_CONDITION_CLOUDY,
    11: ATTR_CONDITION_CLOUDY,
    12: ATTR_CONDITION_RAINY,
    13: ATTR_CONDITION_POURING,
    14: ATTR_CONDITION_SNOWY_RAINY,
    15: ATTR_CONDITION_SNOWY_RAINY,
    16: ATTR_CONDITION_SNOWY,
    17: ATTR_CONDITION_SNOWY,
    18: ATTR_CONDITION_SNOWY,
    19: ATTR_CONDITION_LIGHTNING_RAINY,
    20: None,
    21: None,
    22: ATTR_CONDITION_PARTLYCLOUDY,
    23: ATTR_CONDITION_FOG,
    24: ATTR_CONDITION_FOG,
    25: None,
    26: None,
    27: ATTR_CONDITION_SNOWY_RAINY,
    28: ATTR_CONDITION_RAINY,
    29: None,
    30: ATTR_CONDITION_CLEAR_NIGHT,
    31: ATTR_CONDITION_CLEAR_NIGHT,
    32: ATTR_CONDITION_PARTLYCLOUDY,
    33: ATTR_CONDITION_PARTLYCLOUDY,
    34: ATTR_CONDITION_PARTLYCLOUDY,
    35: ATTR_CONDITION_PARTLYCLOUDY,
    36: ATTR_CONDITION_RAINY,
    37: ATTR_CONDITION_SNOWY_RAINY,
    38: ATTR_CONDITION_SNOWY,
    39: ATTR_CONDITION_LIGHTNING_RAINY,
    40: ATTR_CONDITION_SNOWY,
    41: None,
    42: None,
    43: ATTR_CONDITION_WINDY,
    44: ATTR_CONDITION_EXCEPTIONAL,
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add a weather entity from a config_entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["weather_coordinator"]
    async_add_entities(
        [
            ECWeather(
                coordinator, config_entry.data, hass.config.units.is_metric, False
            ),
            ECWeather(
                coordinator, config_entry.data, hass.config.units.is_metric, True
            ),
        ]
    )


def format_condition(ec_icon):
    """Return condition."""
    try:
        icon_number = int(ec_icon)
    except (TypeError, ValueError):
        return None
    return EC_ICON_TO_HA_CONDITION_MAP.get(icon_number)


class ECWeather(ECBaseEntity, WeatherEntity):
    """Implementation of a EC weather condition."""

    def __init__(self, coordinator, config, is_metric, hourly):
        """Initialise the platform."""
        super().__init__(coordinator, config, "Hourly" if hourly else "")

        self._is_metric = is_metric
        self._hourly = hourly
        self._unique_id_tail = f'weather{"-hourly" if self._hourly else ""}'

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return not self._hourly

    @property
    def condition(self):
        """Return the current condition."""
        return format_condition(self.get_value("icon_code"))

    @property
    def temperature(self):
        """Return the temperature."""
        return self.get_value("temperature")

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def pressure(self):
        """Return the pressure."""
        value = self.get_value("pressure")
        return convert("pressure", value, self._is_metric, PRESSURE_HPA, PRESSURE_INHG)

    @property
    def humidity(self):
        """Return the humidity."""
        return self.get_value("humidity")

    @property
    def wind_speed(self):
        """Return the wind speed."""
        value = self.get_value("wind_speed")
        return convert(
            "wind_speed", value, self._is_metric, LENGTH_KILOMETERS, LENGTH_MILES
        )

    @property
    def wind_bearing(self):
        """Return the wind direction."""
        return self.get_value("wind_bearing")

    @property
    def visibility(self):
        """Return the visibility."""
        value = self.get_value("visibility")
        return convert(
            "visibility", value, self._is_metric, LENGTH_KILOMETERS, LENGTH_MILES
        )

    @property
    def forecast(self):
        """Return the forecast array."""
        return get_forecast(self._coordinator.data, self._hourly)


def get_forecast(data, hourly_forecast):
    """Build the forecast array."""
    forecast_array = []

    if not hourly_forecast:
        half_days = data.daily_forecasts
        if not half_days:
            return None

        today = {
            ATTR_FORECAST_TIME: dt.now().isoformat(),
            ATTR_FORECAST_CONDITION: format_condition(half_days[0]["icon_code"]),
            ATTR_FORECAST_PRECIPITATION_PROBABILITY: int(
                half_days[0]["precip_probability"]
            ),
        }

        if half_days[0]["temperature_class"] == "high":
            today.update(
                {
                    ATTR_FORECAST_TEMP: int(half_days[0]["temperature"]),
                    ATTR_FORECAST_TEMP_LOW: int(half_days[1]["temperature"]),
                }
            )
            half_days = half_days[2:]
        else:
            today.update(
                {
                    ATTR_FORECAST_TEMP: None,
                    ATTR_FORECAST_TEMP_LOW: int(half_days[0]["temperature"]),
                }
            )
            half_days = half_days[1:]

        forecast_array.append(today)

        for day, high, low in zip(range(1, 6), range(0, 9, 2), range(1, 10, 2)):
            forecast_array.append(
                {
                    ATTR_FORECAST_TIME: (
                        dt.now() + datetime.timedelta(days=day)
                    ).isoformat(),
                    ATTR_FORECAST_TEMP: int(half_days[high]["temperature"]),
                    ATTR_FORECAST_TEMP_LOW: int(half_days[low]["temperature"]),
                    ATTR_FORECAST_CONDITION: format_condition(
                        half_days[high]["icon_code"]
                    ),
                    ATTR_FORECAST_PRECIPITATION_PROBABILITY: int(
                        half_days[high]["precip_probability"]
                    ),
                }
            )

    else:
        if not data.hourly_forecasts:
            return None
        for hour in data.hourly_forecasts:
            forecast_array.append(
                {
                    ATTR_FORECAST_TIME: hour["period"],
                    ATTR_FORECAST_TEMP: int(hour["temperature"]),
                    ATTR_FORECAST_CONDITION: format_condition(hour["icon_code"]),
                    ATTR_FORECAST_PRECIPITATION_PROBABILITY: int(
                        hour["precip_probability"]
                    ),
                }
            )

    return forecast_array
