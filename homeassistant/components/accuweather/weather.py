"""Support for the AccuWeather service."""
from __future__ import annotations

from typing import cast

from homeassistant.components.weather import (
    ATTR_FORECAST_CLOUD_COVERAGE,
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_NATIVE_APPARENT_TEMP,
    ATTR_FORECAST_NATIVE_PRECIPITATION,
    ATTR_FORECAST_NATIVE_TEMP,
    ATTR_FORECAST_NATIVE_TEMP_LOW,
    ATTR_FORECAST_NATIVE_WIND_GUST_SPEED,
    ATTR_FORECAST_NATIVE_WIND_SPEED,
    ATTR_FORECAST_PRECIPITATION_PROBABILITY,
    ATTR_FORECAST_TIME,
    ATTR_FORECAST_UV_INDEX,
    ATTR_FORECAST_WIND_BEARING,
    Forecast,
    WeatherEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfLength,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.dt import utc_from_timestamp

from . import AccuWeatherDataUpdateCoordinator
from .const import (
    API_METRIC,
    ATTR_DIRECTION,
    ATTR_FORECAST,
    ATTR_SPEED,
    ATTR_VALUE,
    ATTRIBUTION,
<<<<<<< HEAD
    CONDITION_MAP,
=======
    CONDITION_CLASSES,
>>>>>>> dde6ce6a996 (Add unit tests)
    DOMAIN,
)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add a AccuWeather weather entity from a config_entry."""

    coordinator: AccuWeatherDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([AccuWeatherEntity(coordinator)])


class AccuWeatherEntity(
    CoordinatorEntity[AccuWeatherDataUpdateCoordinator], WeatherEntity
):
    """Define an AccuWeather entity."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, coordinator: AccuWeatherDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_native_precipitation_unit = UnitOfPrecipitationDepth.MILLIMETERS
        self._attr_native_pressure_unit = UnitOfPressure.HPA
        self._attr_native_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_native_visibility_unit = UnitOfLength.KILOMETERS
        self._attr_native_wind_speed_unit = UnitOfSpeed.KILOMETERS_PER_HOUR
        self._attr_unique_id = coordinator.location_key
        self._attr_attribution = ATTRIBUTION
        self._attr_device_info = coordinator.device_info

    @property
    def condition(self) -> str | None:
        """Return the current condition."""
<<<<<<< HEAD
        return CONDITION_MAP.get(self.coordinator.data["WeatherIcon"])
=======
        try:
            return [
                k
                for k, v in CONDITION_CLASSES.items()
                if self.coordinator.data["WeatherIcon"] in v
            ][0]
        except IndexError:
            return None
>>>>>>> dde6ce6a996 (Add unit tests)

    @property
    def cloud_coverage(self) -> float:
        """Return the Cloud coverage in %."""
        return cast(float, self.coordinator.data["CloudCover"])

    @property
    def native_apparent_temperature(self) -> float:
        """Return the apparent temperature."""
        return cast(
            float, self.coordinator.data["ApparentTemperature"][API_METRIC][ATTR_VALUE]
        )

    @property
    def native_temperature(self) -> float:
        """Return the temperature."""
        return cast(float, self.coordinator.data["Temperature"][API_METRIC][ATTR_VALUE])

    @property
    def native_pressure(self) -> float:
        """Return the pressure."""
        return cast(float, self.coordinator.data["Pressure"][API_METRIC][ATTR_VALUE])

    @property
    def native_dew_point(self) -> float:
        """Return the dew point."""
        return cast(float, self.coordinator.data["DewPoint"][API_METRIC][ATTR_VALUE])

    @property
    def humidity(self) -> int:
        """Return the humidity."""
        return cast(int, self.coordinator.data["RelativeHumidity"])

    @property
    def native_wind_gust_speed(self) -> float:
        """Return the wind gust speed."""
        return cast(
            float, self.coordinator.data["WindGust"][ATTR_SPEED][API_METRIC][ATTR_VALUE]
        )

    @property
    def native_wind_speed(self) -> float:
        """Return the wind speed."""
        return cast(
            float, self.coordinator.data["Wind"][ATTR_SPEED][API_METRIC][ATTR_VALUE]
        )

    @property
    def wind_bearing(self) -> int:
        """Return the wind bearing."""
        return cast(int, self.coordinator.data["Wind"][ATTR_DIRECTION]["Degrees"])

    @property
    def native_visibility(self) -> float:
        """Return the visibility."""
        return cast(float, self.coordinator.data["Visibility"][API_METRIC][ATTR_VALUE])

    @property
    def uv_index(self) -> float:
        """Return the UV index."""
        return cast(float, self.coordinator.data["UVIndex"])

    @property
    def forecast(self) -> list[Forecast] | None:
        """Return the forecast array."""
        if not self.coordinator.forecast:
            return None
        # remap keys from library to keys understood by the weather component
        return [
            {
                ATTR_FORECAST_TIME: utc_from_timestamp(item["EpochDate"]).isoformat(),
                ATTR_FORECAST_CLOUD_COVERAGE: item["CloudCoverDay"],
                ATTR_FORECAST_NATIVE_TEMP: item["TemperatureMax"][ATTR_VALUE],
                ATTR_FORECAST_NATIVE_TEMP_LOW: item["TemperatureMin"][ATTR_VALUE],
                ATTR_FORECAST_NATIVE_APPARENT_TEMP: item["RealFeelTemperatureMax"][
                    ATTR_VALUE
                ],
                ATTR_FORECAST_NATIVE_PRECIPITATION: item["TotalLiquidDay"][ATTR_VALUE],
                ATTR_FORECAST_PRECIPITATION_PROBABILITY: item[
                    "PrecipitationProbabilityDay"
                ],
                ATTR_FORECAST_NATIVE_WIND_SPEED: item["WindDay"][ATTR_SPEED][
                    ATTR_VALUE
                ],
                ATTR_FORECAST_NATIVE_WIND_GUST_SPEED: item["WindGustDay"][ATTR_SPEED][
                    ATTR_VALUE
                ],
                ATTR_FORECAST_UV_INDEX: item["UVIndex"][ATTR_VALUE],
                ATTR_FORECAST_WIND_BEARING: item["WindDay"][ATTR_DIRECTION]["Degrees"],
<<<<<<< HEAD
                ATTR_FORECAST_CONDITION: CONDITION_MAP.get(item["IconDay"]),
=======
                ATTR_FORECAST_CONDITION: [
                    k for k, v in CONDITION_CLASSES.items() if item["IconDay"] in v
                ][0],
>>>>>>> dde6ce6a996 (Add unit tests)
            }
            for item in self.coordinator.data[ATTR_FORECAST]
        ]
