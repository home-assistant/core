"""Weather component that handles meteorological data for your location."""
import logging
from typing import Any, Callable, Dict, List, Optional

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_PRECIPITATION,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TEMP_LOW,
    ATTR_FORECAST_TIME,
    ATTR_FORECAST_WIND_BEARING,
    ATTR_FORECAST_WIND_SPEED,
    ATTR_WEATHER_HUMIDITY,
    ATTR_WEATHER_OZONE,
    ATTR_WEATHER_PRESSURE,
    ATTR_WEATHER_VISIBILITY,
    WeatherEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    LENGTH_FEET,
    LENGTH_KILOMETERS,
    LENGTH_METERS,
    LENGTH_MILES,
    PRESSURE_HPA,
    PRESSURE_INHG,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.sun import is_up
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util.distance import convert as distance_convert
from homeassistant.util.pressure import convert as pressure_convert
from homeassistant.util.temperature import convert as temp_convert

from . import ClimaCellDataUpdateCoordinator
from .const import (
    ATTR_WEATHER_CLOUD_COVER,
    ATTR_WEATHER_DEWPOINT,
    ATTR_WEATHER_FEELS_LIKE,
    ATTR_WEATHER_MOON_PHASE,
    ATTR_WEATHER_PRECIPITATION,
    ATTR_WEATHER_PRECIPITATION_TYPE,
    ATTR_WEATHER_WIND_GUST,
    ATTRIBUTION,
    CLEAR_CONDITIONS,
    CONDITIONS,
    CONF_FORECAST_INTERVAL,
    CURRENT,
    DAILY,
    DOMAIN,
    FORECASTS,
    HOURLY,
    WIND_DIRECTIONS,
)

# mypy: allow-untyped-defs, no-check-untyped-defs

_LOGGER = logging.getLogger(__name__)


def _translate_condition(
    hass: HomeAssistantType, condition: Optional[str]
) -> Optional[str]:
    """Translate ClimaCell condition into an HA condition."""
    if "clear" in condition.lower():
        if is_up(hass):
            return CLEAR_CONDITIONS["day"]

        return CLEAR_CONDITIONS["night"]

    return CONDITIONS[condition]


def _translate_wind_direction(direction: Optional[float]) -> Optional[str]:
    """Translate ClimaCell wind direction in degrees to a bearing."""
    return WIND_DIRECTIONS.get(int(direction * 16 / 360))


def _forecast_dict(
    hass: HomeAssistantType,
    condition: str,
    precipitation: str,
    temp: float,
    temp_low: Optional[float],
    time: str,
    wind_direction: Optional[float],
    wind_speed: Optional[float],
    humidity: Optional[float],
    ozone: Optional[float],
    pressure: Optional[float],
    visibility: Optional[float],
) -> Dict[str, Any]:
    """Return formatted Forecast dict from ClimaCell forecast data."""
    wind_bearing = _translate_wind_direction(wind_direction) if wind_direction else None
    translated_condition = _translate_condition(hass, condition) if condition else None
    data = {
        ATTR_FORECAST_CONDITION: translated_condition,
        ATTR_FORECAST_PRECIPITATION: precipitation,
        ATTR_FORECAST_TEMP: temp,
        ATTR_FORECAST_TEMP_LOW: temp_low,
        ATTR_FORECAST_TIME: time,
        ATTR_FORECAST_WIND_BEARING: wind_bearing,
        ATTR_FORECAST_WIND_SPEED: wind_speed,
        ATTR_WEATHER_HUMIDITY: humidity,
        ATTR_WEATHER_OZONE: ozone,
        ATTR_WEATHER_PRESSURE: pressure,
        ATTR_WEATHER_VISIBILITY: visibility,
    }

    return {k: v for k, v in data.items() if v is not None}


async def async_setup_entry(
    hass: HomeAssistantType,
    config_entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], bool], None],
) -> None:
    """Set up a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    entity = ClimaCellWeatherEntity(config_entry, coordinator)

    async_add_entities([entity], update_before_add=True)


class ClimaCellWeatherEntity(WeatherEntity):
    """Entity that talks to ClimaCell API to retrieve weather data."""

    def __init__(
        self, config_entry: ConfigEntry, coordinator: ClimaCellDataUpdateCoordinator
    ) -> None:
        """Initialize ClimaCell Weather Entity."""
        self._config_entry = config_entry
        self._coordinator = coordinator
        self._async_unsub_listeners = []

    async def async_update(self) -> None:
        """Retrieve latest state of the device."""
        await self._coordinator.async_request_refresh()

    async def async_added_to_hass(self) -> None:
        """Connect to dispatcher listening for entity data notifications."""
        self._async_unsub_listeners.append(
            self._coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect callbacks when entity is removed."""
        for listener in self._async_unsub_listeners:
            listener()

        self._async_unsub_listeners.clear()

    @property
    def available(self) -> bool:
        """Return the availabiliity of the entity."""
        return self._coordinator.last_update_success

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return f"{self._config_entry.data[CONF_NAME]}"

    @property
    def unique_id(self) -> str:
        """Return the unique id of the entity."""
        return f"{self._config_entry.unique_id}_weather"

    @property
    def temperature(self):
        """Return the platform temperature."""
        if "temp" not in self._coordinator.data[CURRENT]:
            return None
        temperature = self._coordinator.data[CURRENT]["temp"]["value"]
        if self.hass.config.units.is_metric:
            return temp_convert(temperature, TEMP_FAHRENHEIT, TEMP_CELSIUS)
        return temperature

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        if self.hass.config.units.is_metric:
            return TEMP_CELSIUS
        return TEMP_FAHRENHEIT

    @property
    def pressure(self):
        """Return the pressure."""
        if "baro_pressure" not in self._coordinator.data[CURRENT]:
            return None
        pressure = self._coordinator.data[CURRENT]["baro_pressure"]["value"]
        if self.hass.config.units.is_metric:
            return pressure_convert(pressure, PRESSURE_INHG, PRESSURE_HPA)
        return pressure

    @property
    def pressure_unit(self):
        """Return the pressure unit."""
        if self.hass.config.units.is_metric:
            return PRESSURE_HPA
        return PRESSURE_INHG

    @property
    def humidity(self):
        """Return the humidity."""
        if "humidity" not in self._coordinator.data[CURRENT]:
            return None
        return self._coordinator.data[CURRENT]["humidity"]["value"]

    @property
    def wind_speed(self):
        """Return the wind speed."""
        if "wind_speed" not in self._coordinator.data[CURRENT]:
            return None
        wind_speed = self._coordinator.data[CURRENT]["wind_speed"]["value"]
        if self.hass.config.units.is_metric:
            return distance_convert(wind_speed, LENGTH_MILES, LENGTH_KILOMETERS)
        return wind_speed

    @property
    def wind_bearing(self):
        """Return the wind bearing."""
        if "wind_direction" not in self._coordinator.data[CURRENT]:
            return None
        return _translate_wind_direction(
            self._coordinator.data[CURRENT]["wind_direction"]["value"]
        )

    @property
    def ozone(self):
        """Return the O3 (ozone) level."""
        if "o3" not in self._coordinator.data[CURRENT]:
            return None
        return self._coordinator.data[CURRENT]["o3"]["value"]

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def condition(self):
        """Return the condition."""
        if "weather_code" not in self._coordinator.data[CURRENT]:
            return None
        return _translate_condition(
            self.hass, self._coordinator.data[CURRENT]["weather_code"]["value"]
        )

    @property
    def visibility(self):
        """Return the visibility."""
        if "visibility" not in self._coordinator.data[CURRENT]:
            return None
        visibility = self._coordinator.data[CURRENT]["visibility"]["value"]
        if self.hass.config.units.is_metric:
            return distance_convert(visibility, LENGTH_MILES, LENGTH_KILOMETERS)
        return visibility

    @property
    def wind_gust(self):
        """Return the wind gust speed."""
        if "wind_gust" not in self._coordinator.data[CURRENT]:
            return None
        wind_gust = self._coordinator.data[CURRENT]["wind_gust"]["value"]
        if self.hass.config.units.is_metric:
            return distance_convert(wind_gust, LENGTH_MILES, LENGTH_KILOMETERS)
        return wind_gust

    @property
    def dewpoint(self):
        """Return the dewpoint temperature."""
        if "dewpoint" not in self._coordinator.data[CURRENT]:
            return None
        dewpoint = self._coordinator.data[CURRENT]["dewpoint"]["value"]
        if self.hass.config.units.is_metric:
            return temp_convert(dewpoint, TEMP_FAHRENHEIT, TEMP_CELSIUS)
        return dewpoint

    @property
    def feels_like(self):
        """Return the feels like temperature."""
        if "feels_like" not in self._coordinator.data[CURRENT]:
            return None
        feels_like = self._coordinator.data[CURRENT]["feels_like"]["value"]
        if self.hass.config.units.is_metric:
            return temp_convert(feels_like, TEMP_FAHRENHEIT, TEMP_CELSIUS)
        return feels_like

    @property
    def precipitation(self):
        """Return the precipitation."""
        if "precipitation" not in self._coordinator.data[CURRENT]:
            return None
        precipitation = self._coordinator.data[CURRENT]["precipitation"]["value"]
        if self.hass.config.units.is_metric:
            return (
                distance_convert(precipitation / 12, LENGTH_FEET, LENGTH_METERS) * 1000
            )
        return precipitation

    @property
    def precipitation_type(self):
        """Return the type of precipitation."""
        if "precipitation_type" not in self._coordinator.data[CURRENT]:
            return None

        return self._coordinator.data[CURRENT]["precipitation_type"]["value"]

    @property
    def cloud_cover(self):
        """Return the cloud cover."""
        if "cloud_cover" not in self._coordinator.data[CURRENT]:
            return None
        return self._coordinator.data[CURRENT]["cloud_cover"]["value"]

    @property
    def moon_phase(self):
        """Return the moon phase."""
        if "moon_phase" not in self._coordinator.data[CURRENT]:
            return None
        return self._coordinator.data[CURRENT]["moon_phase"]["value"]

    @property
    def forecast(self):
        """Return the forecast."""
        forecasts = []

        if (
            self._config_entry.data[CONF_FORECAST_INTERVAL] == DAILY
            and self._coordinator.data[FORECASTS]
        ):
            for forecast in self._coordinator.data[FORECASTS]:
                temp_max = None
                temp_min = None
                for item in forecast["temp"]:
                    if "max" in item:
                        temp_max = item["max"]["value"]
                    if "min" in item:
                        temp_min = item["min"]["value"]
                forecasts.append(
                    _forecast_dict(
                        self.hass,
                        forecast["weather_code"]["value"],
                        forecast["precipitation_accumulation"]["value"],
                        temp_max,
                        temp_min,
                        forecast["observation_time"]["value"],
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                    )
                )
            return forecasts

        if (
            self._config_entry.data[CONF_FORECAST_INTERVAL] == HOURLY
            and self._coordinator.data[FORECASTS]
        ):
            for forecast in self._coordinator.data[FORECASTS]:
                forecasts.append(
                    _forecast_dict(
                        self.hass,
                        forecast["weather_code"]["value"],
                        forecast["precipitation"]["value"],
                        forecast["temp"]["value"],
                        None,
                        forecast["observation_time"]["value"],
                        forecast["wind_direction"]["value"],
                        forecast["wind_speed"]["value"],
                        forecast["humidity"]["value"],
                        forecast["o3"]["value"],
                        forecast["baro_pressure"]["value"],
                        forecast["visibility"]["value"],
                    )
                )
            return forecasts

        return None

    @property
    def device_state_attributes(self):
        """Return additional state attributes."""
        data = {}

        if self.feels_like is not None:
            data[ATTR_WEATHER_FEELS_LIKE] = self.feels_like

        if self.dewpoint is not None:
            data[ATTR_WEATHER_DEWPOINT] = self.dewpoint

        if self.wind_gust is not None:
            data[ATTR_WEATHER_WIND_GUST] = self.wind_gust

        if self.precipitation is not None:
            data[ATTR_WEATHER_PRECIPITATION] = self.precipitation

        if self.precipitation_type is not None:
            data[ATTR_WEATHER_PRECIPITATION_TYPE] = self.precipitation_type

        if self.cloud_cover is not None:
            data[ATTR_WEATHER_CLOUD_COVER] = self.cloud_cover

        if self.moon_phase is not None:
            data[ATTR_WEATHER_MOON_PHASE] = self.moon_phase

        return data
