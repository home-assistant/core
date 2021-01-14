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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTRIBUTION,
    CONDITION_CLASSES,
    DEFAULT_NAME,
    DOMAIN,
    METOFFICE_DAILY_COORDINATOR,
    METOFFICE_DATA,
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
            MetOfficeWeather(entry.data, hass_data, True),
            MetOfficeWeather(entry.data, hass_data, False),
        ],
        False,
    )


def _build_forecast_data(timestep):
    data = {}
    data[ATTR_FORECAST_TIME] = timestep.date
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


class MetOfficeWeather(WeatherEntity):
    """Implementation of a Met Office weather condition."""

    def __init__(self, entry_data, hass_data, use_3hourly):
        """Initialise the platform with a data instance."""
        self._data = hass_data[METOFFICE_DATA]
        self._coordinator = (
            hass_data[METOFFICE_HOURLY_COORDINATOR]
            if use_3hourly
            else hass_data[METOFFICE_DAILY_COORDINATOR]
        )

        self._name = f"{DEFAULT_NAME} {hass_data[METOFFICE_NAME]} {MODE_3HOURLY_LABEL if use_3hourly else MODE_DAILY_LABEL}"
        self._unique_id = f"{self._data.latitude}_{self._data.longitude}"
        if not use_3hourly:
            self._unique_id = f"{self._unique_id}_{MODE_DAILY}"

        self.use_3hourly = use_3hourly
        self.metoffice_now = None
        self.metoffice_forecast = None

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
        if self.metoffice_now:
            return _get_weather_condition(self.metoffice_now.weather.value)
        return None

    @property
    def temperature(self):
        """Return the platform temperature."""
        if self.metoffice_now and self.metoffice_now.temperature:
            return self.metoffice_now.temperature.value
        return None

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def visibility(self):
        """Return the platform visibility."""
        _visibility = None
        if hasattr(self.metoffice_now, "visibility"):
            _visibility = f"{VISIBILITY_CLASSES.get(self.metoffice_now.visibility.value)} - {VISIBILITY_DISTANCE_CLASSES.get(self.metoffice_now.visibility.value)}"
        return _visibility

    @property
    def visibility_unit(self):
        """Return the unit of measurement."""
        return LENGTH_KILOMETERS

    @property
    def pressure(self):
        """Return the mean sea-level pressure."""
        if self.metoffice_now and self.metoffice_now.pressure:
            return self.metoffice_now.pressure.value
        return None

    @property
    def humidity(self):
        """Return the relative humidity."""
        if self.metoffice_now and self.metoffice_now.humidity:
            return self.metoffice_now.humidity.value
        return None

    @property
    def wind_speed(self):
        """Return the wind speed."""
        if self.metoffice_now and self.metoffice_now.wind_speed:
            return self.metoffice_now.wind_speed.value
        return None

    @property
    def wind_bearing(self):
        """Return the wind bearing."""
        if self.metoffice_now and self.metoffice_now.wind_direction:
            return self.metoffice_now.wind_direction.value
        return None

    @property
    def forecast(self):
        """Return the forecast array."""
        return [_build_forecast_data(timestep) for timestep in self.metoffice_forecast]

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    async def async_added_to_hass(self) -> None:
        """Set up a listener and load data."""
        self.async_on_remove(
            self._coordinator.async_add_listener(self._update_callback)
        )
        self._update_callback()

    @callback
    def _update_callback(self) -> None:
        """Load data from integration."""
        if self.use_3hourly:
            self.metoffice_now = self._data.now_3hourly
            self.metoffice_forecast = self._data.forecast_3hourly
        else:
            self.metoffice_now = self._data.now_daily
            self.metoffice_forecast = self._data.forecast_daily
        self.async_write_ha_state()

    @property
    def should_poll(self) -> bool:
        """Entities do not individually poll."""
        return False

    @property
    def available(self):
        """Return if state is available."""
        return self.metoffice_now is not None and self.metoffice_forecast is not None
