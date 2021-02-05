"""Support for retrieving meteorological data from FMI (Finnish Meteorological Institute)."""
from dateutil import tz

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_PRECIPITATION,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TIME,
    ATTR_FORECAST_WIND_BEARING,
    ATTR_FORECAST_WIND_SPEED,
    ATTR_WEATHER_HUMIDITY,
    ATTR_WEATHER_PRESSURE,
    WeatherEntity,
)
from homeassistant.const import CONF_NAME
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import get_weather_symbol
from .const import _LOGGER, ATTRIBUTION, COORDINATOR, DOMAIN, MANUFACTURER, NAME

PARALLEL_UPDATES = 1


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add an FMI weather entity from a config_entry."""
    name = config_entry.data[CONF_NAME]

    coordinator = hass.data[DOMAIN][config_entry.entry_id][COORDINATOR]

    async_add_entities([FMIWeatherEntity(name, coordinator)], False)


class FMIWeatherEntity(CoordinatorEntity, WeatherEntity):
    """Define an FMI Weather Entity."""

    def __init__(self, name, coordinator):
        """Initialize FMI weather object."""
        super().__init__(coordinator)
        self._name = name
        self._attrs = {}
        self._unit_system = "Metric"

    @property
    def name(self):
        """Return the name of the place based on Lat/Long."""
        if self.coordinator.current is None:
            return self._name

        return self.coordinator.current.place

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return self.coordinator.unique_id

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self.coordinator.unique_id)},
            "name": NAME,
            "manufacturer": MANUFACTURER,
            "entry_type": "service",
        }

    @property
    def available(self):
        """Return if weather data is available from FMI."""
        if self.coordinator is None:
            return False

        return self.coordinator.current is not None

    @property
    def temperature(self):
        """Return the temperature."""
        if self.coordinator is None:
            return None

        return self.coordinator.current.data.temperature.value

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        if self.coordinator is None:
            return None

        return self.coordinator.current.data.temperature.unit

    @property
    def humidity(self):
        """Return the humidity."""
        if self.coordinator is None:
            return None

        return self.coordinator.current.data.humidity.value

    @property
    def precipitation(self):
        """Return the humidity."""
        if self.coordinator is None:
            return None

        return self.coordinator.current.data.precipitation_amount.value

    @property
    def wind_speed(self):
        """Return the wind speed."""
        if self.coordinator is None:
            return None

        return round(
            self.coordinator.current.data.wind_speed.value * 3.6, 1
        )  # Convert m/s to km/hr

    @property
    def wind_bearing(self):
        """Return the wind bearing."""
        if self.coordinator is None:
            return None

        return self.coordinator.current.data.wind_direction.value

    @property
    def pressure(self):
        """Return the pressure."""
        if self.coordinator is None:
            return None

        return self.coordinator.current.data.pressure.value

    @property
    def condition(self):
        """Return the condition."""
        if self.coordinator is None:
            return None

        return get_weather_symbol(
            self.coordinator.current.data.symbol.value, self.coordinator.hass
        )

    @property
    def forecast(self):
        """Return the forecast array."""
        if self.coordinator is None:
            return None

        if self.coordinator.forecast is None:
            return None

        data = None

        data = [
            {
                ATTR_FORECAST_TIME: forecast.time.astimezone(tz.tzlocal()),
                ATTR_FORECAST_CONDITION: get_weather_symbol(forecast.symbol.value),
                ATTR_FORECAST_TEMP: forecast.temperature.value,
                ATTR_FORECAST_PRECIPITATION: forecast.precipitation_amount.value,
                ATTR_FORECAST_WIND_SPEED: forecast.wind_speed.value,
                ATTR_FORECAST_WIND_BEARING: forecast.wind_direction.value,
                ATTR_WEATHER_PRESSURE: forecast.pressure.value,
                ATTR_WEATHER_HUMIDITY: forecast.humidity.value,
            }
            for forecast in self.coordinator.forecast.forecasts
        ]

        _LOGGER.debug("FMI- Forecast data: %s", data)

        return data
