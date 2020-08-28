"""Support for Meteo-France weather service."""
import logging
import time

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_PRECIPITATION,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TEMP_LOW,
    ATTR_FORECAST_TIME,
    ATTR_FORECAST_WIND_BEARING,
    ATTR_FORECAST_WIND_SPEED,
    WeatherEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MODE, TEMP_CELSIUS
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    ATTRIBUTION,
    CONDITION_CLASSES,
    COORDINATOR_FORECAST,
    DOMAIN,
    FORECAST_MODE_DAILY,
    FORECAST_MODE_HOURLY,
)

_LOGGER = logging.getLogger(__name__)


def format_condition(condition: str):
    """Return condition from dict CONDITION_CLASSES."""
    for key, value in CONDITION_CLASSES.items():
        if condition in value:
            return key
    return condition


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the Meteo-France weather platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR_FORECAST]

    async_add_entities(
        [
            MeteoFranceWeather(
                coordinator,
                entry.options.get(CONF_MODE, FORECAST_MODE_DAILY),
            )
        ],
        True,
    )
    _LOGGER.debug(
        "Weather entity (%s) added for %s.",
        entry.options.get(CONF_MODE, FORECAST_MODE_DAILY),
        coordinator.data.position["name"],
    )


class MeteoFranceWeather(WeatherEntity):
    """Representation of a weather condition."""

    def __init__(self, coordinator: DataUpdateCoordinator, mode: str):
        """Initialise the platform with a data instance and station name."""
        self.coordinator = coordinator
        self._city_name = self.coordinator.data.position["name"]
        self._mode = mode
        self._unique_id = f"{self.coordinator.data.position['lat']},{self.coordinator.data.position['lon']}"

    @property
    def unique_id(self):
        """Return the unique id of the sensor."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._city_name

    @property
    def condition(self):
        """Return the current condition."""
        return format_condition(
            self.coordinator.data.current_forecast["weather"]["desc"]
        )

    @property
    def temperature(self):
        """Return the temperature."""
        return self.coordinator.data.current_forecast["T"]["value"]

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def pressure(self):
        """Return the pressure."""
        return self.coordinator.data.current_forecast["sea_level"]

    @property
    def humidity(self):
        """Return the humidity."""
        return self.coordinator.data.current_forecast["humidity"]

    @property
    def wind_speed(self):
        """Return the wind speed."""
        # convert from API m/s to km/h
        return round(self.coordinator.data.current_forecast["wind"]["speed"] * 3.6)

    @property
    def wind_bearing(self):
        """Return the wind bearing."""
        wind_bearing = self.coordinator.data.current_forecast["wind"]["direction"]
        if wind_bearing != -1:
            return wind_bearing

    @property
    def forecast(self):
        """Return the forecast."""
        forecast_data = []

        if self._mode == FORECAST_MODE_HOURLY:
            today = time.time()
            for forecast in self.coordinator.data.forecast:
                # Can have data in the past
                if forecast["dt"] < today:
                    continue
                forecast_data.append(
                    {
                        ATTR_FORECAST_TIME: dt_util.utc_from_timestamp(
                            forecast["dt"]
                        ).isoformat(),
                        ATTR_FORECAST_CONDITION: format_condition(
                            forecast["weather"]["desc"]
                        ),
                        ATTR_FORECAST_TEMP: forecast["T"]["value"],
                        ATTR_FORECAST_PRECIPITATION: forecast["rain"].get("1h"),
                        ATTR_FORECAST_WIND_SPEED: forecast["wind"]["speed"],
                        ATTR_FORECAST_WIND_BEARING: forecast["wind"]["direction"]
                        if forecast["wind"]["direction"] != -1
                        else None,
                    }
                )
        else:
            for forecast in self.coordinator.data.daily_forecast:
                # stop when we don't have a weather condition (can happen around last days of forcast, max 14)
                if not forecast.get("weather12H"):
                    break
                forecast_data.append(
                    {
                        ATTR_FORECAST_TIME: self.coordinator.data.timestamp_to_locale_time(
                            forecast["dt"]
                        ),
                        ATTR_FORECAST_CONDITION: format_condition(
                            forecast["weather12H"]["desc"]
                        ),
                        ATTR_FORECAST_TEMP: forecast["T"]["max"],
                        ATTR_FORECAST_TEMP_LOW: forecast["T"]["min"],
                        ATTR_FORECAST_PRECIPITATION: forecast["precipitation"]["24h"],
                    }
                )
        return forecast_data

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def available(self):
        """Return if state is available."""
        return self.coordinator.last_update_success

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    async def async_update(self):
        """Only used by the generic entity update service."""
        if not self.enabled:
            return

        await self.coordinator.async_request_refresh()

    async def async_added_to_hass(self):
        """Subscribe to updates."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )
