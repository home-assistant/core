"""Weather platform for the HERE Destination Weather service."""
from __future__ import annotations

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_PRECIPITATION,
    ATTR_FORECAST_PRECIPITATION_PROBABILITY,
    ATTR_FORECAST_PRESSURE,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TEMP_LOW,
    ATTR_FORECAST_TIME,
    ATTR_FORECAST_WIND_BEARING,
    ATTR_FORECAST_WIND_SPEED,
    Forecast,
    WeatherEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME, TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import (
    CONDITION_CLASSES,
    DEFAULT_MODE,
    DOMAIN,
    MODE_ASTRONOMY,
    MODE_DAILY_SIMPLE,
    SENSOR_TYPES,
)
from .utils import (
    convert_temperature_unit_of_measurement_if_needed,
    get_attribute_from_here_data,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Add here_weather entities from a ConfigEntry."""
    here_weather_coordinators = hass.data[DOMAIN][entry.entry_id]

    entities_to_add = []
    for sensor_type in SENSOR_TYPES:
        if sensor_type != MODE_ASTRONOMY:
            entities_to_add.append(
                HEREDestinationWeather(
                    entry,
                    here_weather_coordinators[sensor_type],
                    sensor_type,
                )
            )
    async_add_entities(entities_to_add)


class HEREDestinationWeather(CoordinatorEntity, WeatherEntity):
    """Implementation of an HERE Destination Weather WeatherEntity."""

    def __init__(
        self, entry: ConfigEntry, coordinator: DataUpdateCoordinator, mode: str
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._name = entry.data[CONF_NAME]
        self._mode = mode
        self._unique_id = "".join(
            f"{entry.data[CONF_LATITUDE]}_{entry.data[CONF_LONGITUDE]}_{self._mode}".lower().split()
        )

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._name} {self._mode}"

    @property
    def unique_id(self):
        """Set unique_id for sensor."""
        return self._unique_id

    @property
    def condition(self) -> str | None:
        """Return the current condition."""
        return get_condition_from_here_data(self.coordinator.data)

    @property
    def temperature(self) -> float | None:
        """Return the temperature."""
        return get_temperature_from_here_data(self.coordinator.data, self._mode)

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        return convert_temperature_unit_of_measurement_if_needed(
            self.coordinator.hass.config.units.name, TEMP_CELSIUS
        )

    @property
    def pressure(self) -> float | None:
        """Return the pressure."""
        return get_pressure_from_here_data(self.coordinator.data, self._mode)

    @property
    def humidity(self) -> float | None:
        """Return the humidity."""
        if (
            humidity := get_attribute_from_here_data(self.coordinator.data, "humidity")
        ) is not None:
            return float(humidity)
        return None

    @property
    def wind_speed(self) -> float | None:
        """Return the wind speed."""
        return get_wind_speed_from_here_data(self.coordinator.data)

    @property
    def wind_bearing(self) -> float | str | None:
        """Return the wind bearing."""
        return get_wind_bearing_from_here_data(self.coordinator.data)

    @property
    def attribution(self) -> str | None:
        """Return the attribution."""
        return None

    @property
    def visibility(self) -> float | None:
        """Return the visibility."""
        if "visibility" in SENSOR_TYPES[self._mode]:
            if (
                visibility := get_attribute_from_here_data(
                    self.coordinator.data, "visibility"
                )
            ) is not None:
                return float(visibility)
        return None

    @property
    def forecast(self) -> list[Forecast] | None:
        """Return the forecast array."""
        data: list[Forecast] = []
        for offset in range(len(self.coordinator.data)):
            data.append(
                {
                    ATTR_FORECAST_CONDITION: get_condition_from_here_data(
                        self.coordinator.data, offset
                    ),
                    ATTR_FORECAST_TIME: get_time_from_here_data(
                        self.coordinator.data, offset
                    ),
                    ATTR_FORECAST_PRECIPITATION_PROBABILITY: get_precipitation_probability(
                        self.coordinator.data, self._mode, offset
                    ),
                    ATTR_FORECAST_PRECIPITATION: calc_precipitation(
                        self.coordinator.data, offset
                    ),
                    ATTR_FORECAST_PRESSURE: get_pressure_from_here_data(
                        self.coordinator.data, self._mode, offset
                    ),
                    ATTR_FORECAST_TEMP: get_high_or_default_temperature_from_here_data(
                        self.coordinator.data, self._mode, offset
                    ),
                    ATTR_FORECAST_TEMP_LOW: get_low_or_default_temperature_from_here_data(
                        self.coordinator.data, self._mode, offset
                    ),
                    ATTR_FORECAST_WIND_BEARING: get_wind_bearing_from_here_data(
                        self.coordinator.data, offset
                    ),
                    ATTR_FORECAST_WIND_SPEED: get_wind_speed_from_here_data(
                        self.coordinator.data, offset
                    ),
                }
            )
        return data

    @property
    def entity_registry_enabled_default(self):
        """Return if the entity should be enabled when first added to the entity registry."""
        return self._mode == DEFAULT_MODE

    @property
    def device_info(self) -> DeviceInfo:
        """Return a device description for device registry."""
        return {
            "identifiers": {(DOMAIN, self._unique_id)},
            "name": self.name,
            "manufacturer": "here.com",
            "entry_type": "service",
        }


def get_wind_speed_from_here_data(here_data: list, offset: int = 0) -> float:
    """Return the wind speed from here_data."""
    wind_speed = get_attribute_from_here_data(here_data, "windSpeed", offset)
    assert wind_speed is not None
    return float(wind_speed)


def get_wind_bearing_from_here_data(here_data: list, offset: int = 0) -> int:
    """Return the wind bearing from here_data."""
    wind_bearing = get_attribute_from_here_data(here_data, "windDirection", offset)
    assert wind_bearing is not None
    return int(wind_bearing)


def get_time_from_here_data(here_data: list, offset: int = 0) -> str:
    """Return the time from here_data."""
    time = get_attribute_from_here_data(here_data, "utcTime", offset)
    assert time is not None
    return time


def get_pressure_from_here_data(
    here_data: list, mode: str, offset: int = 0
) -> float | None:
    """Return the pressure from here_data."""
    if "barometerPressure" in SENSOR_TYPES[mode]:
        if (
            pressure := get_attribute_from_here_data(
                here_data, "barometerPressure", offset
            )
        ) is not None:
            return float(pressure)
    return None


def get_precipitation_probability(
    here_data: list, mode: str, offset: int = 0
) -> int | None:
    """Return the precipitation probability from here_data."""
    if "precipitationProbability" in SENSOR_TYPES[mode]:
        if (
            precipitation_probability := get_attribute_from_here_data(
                here_data, "precipitationProbability", offset
            )
        ) is not None:
            return int(precipitation_probability)
    return None


def get_condition_from_here_data(here_data: list, offset: int = 0) -> str | None:
    """Return the condition from here_data."""
    return next(
        (
            k
            for k, v in CONDITION_CLASSES.items()
            if get_attribute_from_here_data(here_data, "iconName", offset) in v
        ),
        None,
    )


def get_high_or_default_temperature_from_here_data(
    here_data: list, mode: str, offset: int = 0
) -> float | None:
    """Return the temperature from here_data."""
    temperature = get_attribute_from_here_data(here_data, "highTemperature", offset)
    if temperature is not None:
        return float(temperature)

    return get_temperature_from_here_data(here_data, mode, offset)


def get_low_or_default_temperature_from_here_data(
    here_data: list, mode: str, offset: int = 0
) -> float | None:
    """Return the temperature from here_data."""
    temperature = get_attribute_from_here_data(here_data, "lowTemperature", offset)
    if temperature is not None:
        return float(temperature)
    return get_temperature_from_here_data(here_data, mode, offset)


def get_temperature_from_here_data(
    here_data: list, mode: str, offset: int = 0
) -> float | None:
    """Return the temperature from here_data."""
    if mode == MODE_DAILY_SIMPLE:
        temperature = get_attribute_from_here_data(here_data, "highTemperature", offset)
    else:
        temperature = get_attribute_from_here_data(here_data, "temperature", offset)
    if temperature is not None:
        return float(temperature)
    return None


def calc_precipitation(here_data: list, offset: int = 0) -> float | None:
    """Calculate Precipitation."""
    rain_fall = get_attribute_from_here_data(here_data, "rainFall", offset)
    snow_fall = get_attribute_from_here_data(here_data, "snowFall", offset)
    if rain_fall is not None and snow_fall is not None:
        return float(rain_fall) + float(snow_fall)
    return None
