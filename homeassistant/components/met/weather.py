"""Support for Met.no weather service."""
from __future__ import annotations

import logging
from types import MappingProxyType
from typing import Any

import voluptuous as vol

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TIME,
    ATTR_WEATHER_HUMIDITY,
    ATTR_WEATHER_PRESSURE,
    ATTR_WEATHER_TEMPERATURE,
    ATTR_WEATHER_WIND_BEARING,
    ATTR_WEATHER_WIND_SPEED,
    PLATFORM_SCHEMA,
    Forecast,
    WeatherEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_ELEVATION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    LENGTH_INCHES,
    LENGTH_MILLIMETERS,
    PRESSURE_HPA,
    PRESSURE_INHG,
    SPEED_KILOMETERS_PER_HOUR,
    SPEED_MILES_PER_HOUR,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    T,
)
from homeassistant.util.distance import convert as convert_distance
from homeassistant.util.pressure import convert as convert_pressure
from homeassistant.util.speed import convert as convert_speed

from .const import (
    ATTR_FORECAST_PRECIPITATION,
    ATTR_MAP,
    CONDITIONS_MAP,
    CONF_TRACK_HOME,
    DOMAIN,
    FORECAST_MAP,
)

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = (
    "Weather forecast from met.no, delivered by the Norwegian "
    "Meteorological Institute."
)
DEFAULT_NAME = "Met.no"


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Inclusive(
            CONF_LATITUDE, "coordinates", "Latitude and longitude must exist together"
        ): cv.latitude,
        vol.Inclusive(
            CONF_LONGITUDE, "coordinates", "Latitude and longitude must exist together"
        ): cv.longitude,
        vol.Optional(CONF_ELEVATION): int,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Met.no weather platform."""
    _LOGGER.warning("Loading Met.no via platform config is deprecated")

    # Add defaults.
    config = {CONF_ELEVATION: hass.config.elevation, **config}

    if config.get(CONF_LATITUDE) is None:
        config[CONF_TRACK_HOME] = True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add a weather entity from a config_entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        [
            MetWeather(
                coordinator, config_entry.data, hass.config.units.is_metric, False
            ),
            MetWeather(
                coordinator, config_entry.data, hass.config.units.is_metric, True
            ),
        ]
    )


def format_condition(condition: str) -> str:
    """Return condition from dict CONDITIONS_MAP."""
    for key, value in CONDITIONS_MAP.items():
        if condition in value:
            return key
    return condition


class MetWeather(CoordinatorEntity, WeatherEntity):
    """Implementation of a Met.no weather condition."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[T],
        config: MappingProxyType[str, Any],
        is_metric: bool,
        hourly: bool,
    ) -> None:
        """Initialise the platform with a data instance and site."""
        super().__init__(coordinator)
        self._config = config
        self._is_metric = is_metric
        self._hourly = hourly

    @property
    def track_home(self) -> (Any | bool):
        """Return if we are tracking home."""
        return self._config.get(CONF_TRACK_HOME, False)

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        name_appendix = ""
        if self._hourly:
            name_appendix = "-hourly"
        if self.track_home:
            return f"home{name_appendix}"

        return f"{self._config[CONF_LATITUDE]}-{self._config[CONF_LONGITUDE]}{name_appendix}"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        name = self._config.get(CONF_NAME)
        name_appendix = ""
        if self._hourly:
            name_appendix = " Hourly"

        if name is not None:
            return f"{name}{name_appendix}"

        if self.track_home:
            return f"{self.hass.config.location_name}{name_appendix}"

        return f"{DEFAULT_NAME}{name_appendix}"

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return not self._hourly

    @property
    def condition(self) -> str | None:
        """Return the current condition."""
        condition = self.coordinator.data.current_weather_data.get("condition")
        return format_condition(condition)

    @property
    def temperature(self) -> float | None:
        """Return the temperature."""
        return self.coordinator.data.current_weather_data.get(
            ATTR_MAP[ATTR_WEATHER_TEMPERATURE]
        )

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def pressure(self) -> float | None:
        """Return the pressure."""
        pressure_hpa = self.coordinator.data.current_weather_data.get(
            ATTR_MAP[ATTR_WEATHER_PRESSURE]
        )
        if self._is_metric or pressure_hpa is None:
            return pressure_hpa

        return round(convert_pressure(pressure_hpa, PRESSURE_HPA, PRESSURE_INHG), 2)

    @property
    def humidity(self) -> float | None:
        """Return the humidity."""
        return self.coordinator.data.current_weather_data.get(
            ATTR_MAP[ATTR_WEATHER_HUMIDITY]
        )

    @property
    def wind_speed(self) -> float | None:
        """Return the wind speed."""
        speed_km_h = self.coordinator.data.current_weather_data.get(
            ATTR_MAP[ATTR_WEATHER_WIND_SPEED]
        )
        if self._is_metric or speed_km_h is None:
            return speed_km_h

        speed_mi_h = convert_speed(
            speed_km_h, SPEED_KILOMETERS_PER_HOUR, SPEED_MILES_PER_HOUR
        )
        return int(round(speed_mi_h))

    @property
    def wind_bearing(self) -> float | str | None:
        """Return the wind direction."""
        return self.coordinator.data.current_weather_data.get(
            ATTR_MAP[ATTR_WEATHER_WIND_BEARING]
        )

    @property
    def attribution(self) -> str:
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def forecast(self) -> list[Forecast] | None:
        """Return the forecast array."""
        if self._hourly:
            met_forecast = self.coordinator.data.hourly_forecast
        else:
            met_forecast = self.coordinator.data.daily_forecast
        required_keys = {ATTR_FORECAST_TEMP, ATTR_FORECAST_TIME}
        ha_forecast: list[Forecast] = []
        for met_item in met_forecast:
            if not set(met_item).issuperset(required_keys):
                continue
            ha_item = {
                k: met_item[v]
                for k, v in FORECAST_MAP.items()
                if met_item.get(v) is not None
            }
            if not self._is_metric and ATTR_FORECAST_PRECIPITATION in ha_item:
                if ha_item[ATTR_FORECAST_PRECIPITATION] is not None:
                    precip_inches = convert_distance(
                        ha_item[ATTR_FORECAST_PRECIPITATION],
                        LENGTH_MILLIMETERS,
                        LENGTH_INCHES,
                    )
                ha_item[ATTR_FORECAST_PRECIPITATION] = round(precip_inches, 2)
            if ha_item.get(ATTR_FORECAST_CONDITION):
                ha_item[ATTR_FORECAST_CONDITION] = format_condition(
                    ha_item[ATTR_FORECAST_CONDITION]
                )
            ha_forecast.append(ha_item)  # type: ignore[arg-type]
        return ha_forecast

    @property
    def device_info(self) -> DeviceInfo:
        """Device info."""
        return DeviceInfo(
            default_name="Forecast",
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN,)},  # type: ignore[arg-type]
            manufacturer="Met.no",
            model="Forecast",
        )
