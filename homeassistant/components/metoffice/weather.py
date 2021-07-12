"""Support for UK Met Office weather service."""
from datapoint.Day import Day
from datapoint.Timestep import Timestep

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_PRECIPITATION_PROBABILITY,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TEMP_LOW,
    ATTR_FORECAST_TIME,
    ATTR_FORECAST_WIND_BEARING,
    ATTR_FORECAST_WIND_SPEED,
    WeatherEntity,
)
from homeassistant.const import LENGTH_KILOMETERS, TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.dt import utcnow

from .const import (
    ATTRIBUTION,
    CONDITION_CLASSES,
    DEFAULT_NAME,
    DOMAIN,
    METOFFICE_COORDINATES,
    METOFFICE_COORDINATOR,
    METOFFICE_NAME,
    MODE_3HOURLY_LABEL,
    MODE_DAILY,
    MODE_DAILY_LABEL,
    VISIBILITY_CLASSES,
    VISIBILITY_DISTANCE_CLASSES,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigType, async_add_entities
) -> None:
    """Set up the Met Office weather sensor platform."""
    hass_data = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            MetOfficeWeather(hass_data[METOFFICE_COORDINATOR], hass_data, True),
            MetOfficeWeather(hass_data[METOFFICE_COORDINATOR], hass_data, False),
        ],
        False,
    )


def _build_forecast_data(timestep: Timestep):
    data = {}
    data[ATTR_FORECAST_TIME] = timestep.date.isoformat()
    if timestep.weather:
        data[ATTR_FORECAST_CONDITION] = _get_weather_condition(timestep.weather.value)
    if timestep.precipitation:
        data[ATTR_FORECAST_PRECIPITATION_PROBABILITY] = timestep.precipitation.value
    if timestep.temperature:
        data[ATTR_FORECAST_TEMP] = timestep.temperature.value
    if timestep.wind_direction:
        data[ATTR_FORECAST_WIND_BEARING] = timestep.wind_direction.value
    if timestep.wind_speed:
        data[ATTR_FORECAST_WIND_SPEED] = timestep.wind_speed.value
    return data


def _build_daily_forecast_data(day: Day):
    data = {}
    data[ATTR_FORECAST_TIME] = day.date.isoformat()

    timesteps = day.timesteps

    # Use closest timestep to noon to take weather value
    weather_timestep = min(timesteps, key=lambda item: abs(item.date.hour - 12))

    temperature = max(
        [
            timestep.temperature.value if timestep.temperature else -1000
            for timestep in timesteps
        ]
    )
    temperature = temperature if temperature > -1000 else None

    templow = min(
        [
            timestep.temperature.value if timestep.temperature else 1000
            for timestep in timesteps
        ]
    )
    templow = templow if templow < 1000 else None

    # Taking max precipitation probability
    precipitation = max(
        [
            timestep.precipitation.value if timestep.precipitation else 0
            for timestep in timesteps
        ]
    )

    max_wind_timestep: Timestep = max(
        timesteps, key=lambda item: item.wind_speed.value if item.wind_speed else 0
    )

    if weather_timestep:
        data[ATTR_FORECAST_CONDITION] = _get_weather_condition(
            weather_timestep.weather.value
        )
    if precipitation:
        data[ATTR_FORECAST_PRECIPITATION_PROBABILITY] = precipitation
    if temperature:
        data[ATTR_FORECAST_TEMP] = temperature
    if templow:
        data[ATTR_FORECAST_TEMP_LOW] = templow
    if max_wind_timestep.wind_direction:
        data[ATTR_FORECAST_WIND_BEARING] = max_wind_timestep.wind_direction.value
    if max_wind_timestep.wind_speed:
        data[ATTR_FORECAST_WIND_SPEED] = max_wind_timestep.wind_speed.value

    return data


def _get_weather_condition(metoffice_code):
    for hass_name, metoffice_codes in CONDITION_CLASSES.items():
        if metoffice_code in metoffice_codes:
            return hass_name
    return None


class MetOfficeWeather(CoordinatorEntity, WeatherEntity):
    """Implementation of a Met Office weather condition."""

    def __init__(self, coordinator, hass_data, use_3hourly):
        """Initialise the platform with a data instance."""
        super().__init__(coordinator)

        mode_label = MODE_3HOURLY_LABEL if use_3hourly else MODE_DAILY_LABEL
        self._name = f"{DEFAULT_NAME} {hass_data[METOFFICE_NAME]} {mode_label}"
        self._unique_id = hass_data[METOFFICE_COORDINATES]
        if not use_3hourly:
            self._unique_id = f"{self._unique_id}_{MODE_DAILY}"
        self.use_3hourly = use_3hourly

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique of the sensor."""
        return self._unique_id

    @property
    def condition(self):
        """Return the current condition."""
        if self.coordinator.data.now:
            return _get_weather_condition(self.coordinator.data.now.weather.value)
        return None

    @property
    def temperature(self):
        """Return the platform temperature."""
        if self.coordinator.data.now.temperature:
            return self.coordinator.data.now.temperature.value
        return None

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def visibility(self):
        """Return the platform visibility."""
        _visibility = None
        weather_now = self.coordinator.data.now
        if hasattr(weather_now, "visibility"):
            visibility_class = VISIBILITY_CLASSES.get(weather_now.visibility.value)
            visibility_distance = VISIBILITY_DISTANCE_CLASSES.get(
                weather_now.visibility.value
            )
            _visibility = f"{visibility_class} - {visibility_distance}"
        return _visibility

    @property
    def visibility_unit(self):
        """Return the unit of measurement."""
        return LENGTH_KILOMETERS

    @property
    def pressure(self):
        """Return the mean sea-level pressure."""
        weather_now = self.coordinator.data.now
        if weather_now and weather_now.pressure:
            return weather_now.pressure.value
        return None

    @property
    def humidity(self):
        """Return the relative humidity."""
        weather_now = self.coordinator.data.now
        if weather_now and weather_now.humidity:
            return weather_now.humidity.value
        return None

    @property
    def wind_speed(self):
        """Return the wind speed."""
        weather_now = self.coordinator.data.now
        if weather_now and weather_now.wind_speed:
            return weather_now.wind_speed.value
        return None

    @property
    def wind_bearing(self):
        """Return the wind bearing."""
        weather_now = self.coordinator.data.now
        if weather_now and weather_now.wind_direction:
            return weather_now.wind_direction.value
        return None

    @property
    def forecast(self):
        """Return the forecast array."""
        if self.coordinator.data.forecast is None:
            return None
        time_now = utcnow()

        if self.use_3hourly:
            return [
                _build_forecast_data(timestep)
                for day in self.coordinator.data.forecast
                for timestep in day.timesteps
                if timestep.date > time_now
            ]

        return [
            _build_daily_forecast_data(day)
            for day in self.coordinator.data.forecast
            if day.date > time_now
        ]

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION
