"""Support for Environment Canada (EC) weather service."""
from __future__ import annotations

import datetime
import logging

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_PRECIPITATION_PROBABILITY,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TEMP_LOW,
    ATTR_FORECAST_TIME,
    WeatherEntity,
)
from homeassistant.const import (
    CONF_NAME,
    LENGTH_KILOMETERS,
    LENGTH_MILES,
    PRESSURE_HPA,
    PRESSURE_INHG,
    TEMP_CELSIUS,
)
from homeassistant.util import dt
from homeassistant.util.distance import convert as convert_distance
from homeassistant.util.pressure import convert as convert_pressure

from . import ECBaseEntity
from .const import DEFAULT_NAME, DOMAIN, EC_ICON_TO_HA_CONDITION_MAP

_LOGGER = logging.getLogger(__name__)


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


def format_condition(ec_icon: str) -> str | None:
    """Return condition."""
    try:
        icon_number = int(ec_icon)
    except ValueError:
        return None
    return EC_ICON_TO_HA_CONDITION_MAP.get(icon_number)


class ECWeather(ECBaseEntity, WeatherEntity):
    """Implementation of a EC weather condition."""

    def __init__(self, coordinator, config, is_metric, hourly):
        """Initialise the platform."""
        name = f"{config.get(CONF_NAME, DEFAULT_NAME)}{' Hourly' if hourly else ''}"
        super().__init__(coordinator, config, name)

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
        if self.get_value("pressure") is None:
            return None
        pressure_hpa = 10 * float(
            self._coordinator.data.conditions["pressure"]["value"]
        )
        if self._is_metric:
            return pressure_hpa

        return round(convert_pressure(pressure_hpa, PRESSURE_HPA, PRESSURE_INHG), 2)

    @property
    def humidity(self):
        """Return the humidity."""
        return self.get_value("humidity")

    @property
    def wind_speed(self):
        """Return the wind speed."""
        speed_km_h = self.get_value("wind_speed")
        if self._is_metric or speed_km_h is None:
            return speed_km_h

        speed_mi_h = convert_distance(speed_km_h, LENGTH_KILOMETERS, LENGTH_MILES)
        return int(round(speed_mi_h))

    @property
    def wind_bearing(self):
        """Return the wind direction."""
        return self.get_value("wind_bearing")

    @property
    def visibility(self):
        """Return the visibility."""
        visibility = self.get_value("visibility")
        if self._is_metric or visibility is None:
            return visibility

        visibility = convert_distance(visibility, LENGTH_KILOMETERS, LENGTH_MILES)
        return visibility

    @property
    def forecast(self):
        """Return the forecast array."""
        return get_forecast(self._coordinator.data, self._hourly)


def get_forecast(data, hourly_forecast):
    """Build the forecast array."""
    forecast_array = []

    if not hourly_forecast:
        half_days = data.daily_forecasts

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
