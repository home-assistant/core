"""Support for UK Met Office weather service."""
import logging

import datapoint as dp
import voluptuous as vol

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_PRECIPITATION,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TIME,
    ATTR_FORECAST_WIND_BEARING,
    ATTR_FORECAST_WIND_SPEED,
    PLATFORM_SCHEMA,
    WeatherEntity,
)
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_MODE,
    CONF_NAME,
    TEMP_CELSIUS,
)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTRIBUTION,
    CONDITION_CLASSES,
    DEFAULT_NAME,
    MODE_3HOURLY,
    MODE_DAILY,
    VISIBILITY_CLASSES,
)
from .sensor import MetOfficeCurrentData

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_MODE, default=MODE_3HOURLY): vol.In(
            [MODE_3HOURLY, MODE_DAILY]
        ),
        vol.Inclusive(
            CONF_LATITUDE, "coordinates", "Latitude and longitude must exist together"
        ): cv.latitude,
        vol.Inclusive(
            CONF_LONGITUDE, "coordinates", "Latitude and longitude must exist together"
        ): cv.longitude,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Met Office weather platform."""
    latitude = config.get(CONF_LATITUDE)
    longitude = config.get(CONF_LONGITUDE)
    name = config.get(CONF_NAME)
    mode = config.get(CONF_MODE)

    try:
        datapoint = dp.connection(api_key=config.get(CONF_API_KEY))
    except dp.exceptions.APIException as err:
        _LOGGER.error("Received error from Met Office Datapoint: %s", err)
        return

    data = None

    if None in (latitude, longitude):
        _LOGGER.debug("No specific location set in config, tracking HASS settings")
        latitude = hass.config.latitude
        longitude = hass.config.longitude

        @callback
        def track_core_config_changes(event):
            _LOGGER.debug(
                f"Informed of change in core configuration: {event.event_type} / {event.data} / {event.origin} / {event.time_fired} / {event.context}"
            )

            if data is not None:
                _LOGGER.debug("Updating weather MetOfficeCurrentData with new site")

                try:
                    data.site = datapoint.get_nearest_site(
                        latitude=event.data["latitude"],
                        longitude=event.data["longitude"],
                    )
                except dp.exceptions.APIException as err:
                    _LOGGER.error("Received error from Met Office Datapoint: %s", err)
                    return

        hass.bus.listen("core_config_updated", track_core_config_changes)

    else:
        _LOGGER.debug("Specific location set, tracking changes")

        @callback
        def track_config_entry_changes(event):
            _LOGGER.debug("Informed of change in config entry")

        # TODO: listen to config changes for this platform entry

    try:
        site = datapoint.get_nearest_site(latitude=latitude, longitude=longitude)
    except dp.exceptions.APIException as err:
        _LOGGER.error("Received error from Met Office Datapoint: %s", err)
        return

    if not site:
        _LOGGER.error("Unable to get nearest Met Office forecast site")
        return

    data = MetOfficeCurrentData(hass, datapoint, site, mode)
    try:
        data.update()
    except (ValueError, dp.exceptions.APIException) as err:
        _LOGGER.error("Received error from Met Office Datapoint: %s", err)
        return

    add_entities([MetOfficeWeather(name, data)])


class MetOfficeWeather(WeatherEntity):
    """Implementation of a Met Office weather condition."""

    def __init__(self, name, data):
        """Initialise the platform with a data instance and site."""
        self._name = name
        self.data = data

    def update(self):
        """Update current conditions."""
        self.data.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._name} {self.data.site.name}"

    @property
    def icon(self):
        """Return the icon for the current condition."""
        return f"mdi:weather-{self.condition}"

    @property
    def condition(self):
        """Return the current condition."""
        return [
            k for k, v in CONDITION_CLASSES.items() if self.data.now.weather.value in v
        ][0]

    @property
    def temperature(self):
        """Return the platform temperature."""
        return self.data.now.temperature.value

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def pressure(self):
        """Return the mean sea-level pressure."""
        return self.data.now.pressure.value if self.data.now.pressure else None

    @property
    def humidity(self):
        """Return the relative humidity."""
        return self.data.now.humidity.value

    @property
    def visibility(self):
        """Return the visibility range."""
        return (
            VISIBILITY_CLASSES[self.data.now.visibility.value]
            if self.data.now.visibility
            else None
        )

    @property
    def wind_speed(self):
        """Return the wind speed."""
        return self.data.now.wind_speed.value

    @property
    def wind_bearing(self):
        """Return the wind bearing."""
        return self.data.now.wind_direction.value

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def forecast(self):
        """Return the forecast array."""
        data = None
        if self.data.mode == MODE_3HOURLY:
            data = [
                {
                    ATTR_FORECAST_CONDITION: [
                        k
                        for k, v in CONDITION_CLASSES.items()
                        if timestep.weather.value in v
                    ][0]
                    if timestep.weather
                    else None,
                    ATTR_FORECAST_PRECIPITATION: timestep.precipitation.value
                    if timestep.precipitation
                    else None,
                    ATTR_FORECAST_TEMP: timestep.temperature.value
                    if timestep.temperature
                    else None,
                    ATTR_FORECAST_TIME: timestep.date,
                    ATTR_FORECAST_WIND_BEARING: timestep.wind_direction.value
                    if timestep.wind_direction
                    else None,
                    ATTR_FORECAST_WIND_SPEED: timestep.wind_speed.value
                    if timestep.wind_speed
                    else None,
                }
                for timestep in self.data.all.timesteps
            ]
        else:
            data = [
                {
                    ATTR_FORECAST_CONDITION: [
                        k
                        for k, v in CONDITION_CLASSES.items()
                        if timestep.weather.value in v
                    ][0]
                    if timestep.weather
                    else None,
                    ATTR_FORECAST_PRECIPITATION: timestep.precipitation.value
                    if timestep.precipitation
                    else None,
                    ATTR_FORECAST_TEMP: timestep.temperature.value
                    if timestep.temperature
                    else None,
                    ATTR_FORECAST_TIME: timestep.date,
                    ATTR_FORECAST_WIND_BEARING: timestep.wind_direction.value
                    if timestep.wind_direction
                    else None,
                    ATTR_FORECAST_WIND_SPEED: timestep.wind_speed.value
                    if timestep.wind_speed
                    else None,
                }
                for day in self.data.all
                for timestep in day.timesteps
            ]

        return data
