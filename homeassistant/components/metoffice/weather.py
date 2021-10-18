"""Support for UK Met Office weather service."""
from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_PRECIPITATION,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TIME,
    ATTR_FORECAST_WIND_BEARING,
    ATTR_FORECAST_WIND_SPEED,
    WeatherEntity,
)
from homeassistant.const import LENGTH_KILOMETERS, TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTRIBUTION,
    CONDITION_CLASSES,
    DEFAULT_NAME,
    DOMAIN,
    METOFFICE_COORDINATES,
    METOFFICE_DAILY_COORDINATOR,
    METOFFICE_HOURLY_COORDINATOR,
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
            MetOfficeWeather(hass_data[METOFFICE_HOURLY_COORDINATOR], hass_data, True),
            MetOfficeWeather(hass_data[METOFFICE_DAILY_COORDINATOR], hass_data, False),
        ],
        False,
    )


def _build_forecast_data(timestep):
    data = {}
    data[ATTR_FORECAST_TIME] = timestep.date.isoformat()
    if timestep.weather:
        data[ATTR_FORECAST_CONDITION] = _get_weather_condition(timestep.weather.value)
    if timestep.precipitation:
        data[ATTR_FORECAST_PRECIPITATION] = timestep.precipitation.value
    if timestep.temperature:
        data[ATTR_FORECAST_TEMP] = timestep.temperature.value
    if timestep.wind_direction:
        data[ATTR_FORECAST_WIND_BEARING] = timestep.wind_direction.value
    if timestep.wind_speed:
        data[ATTR_FORECAST_WIND_SPEED] = timestep.wind_speed.value
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
        return [
            _build_forecast_data(timestep)
            for timestep in self.coordinator.data.forecast
        ]

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION
