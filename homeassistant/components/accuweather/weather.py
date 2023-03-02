"""Support for the AccuWeather service."""
from __future__ import annotations

from statistics import mean
from typing import Any, cast

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_NATIVE_PRECIPITATION,
    ATTR_FORECAST_NATIVE_TEMP,
    ATTR_FORECAST_NATIVE_TEMP_LOW,
    ATTR_FORECAST_NATIVE_WIND_SPEED,
    ATTR_FORECAST_PRECIPITATION_PROBABILITY,
    ATTR_FORECAST_TIME,
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
from homeassistant.util.unit_system import METRIC_SYSTEM

from . import AccuWeatherDataUpdateCoordinator
from .const import (
    API_IMPERIAL,
    API_METRIC,
    ATTR_FORECAST,
    ATTRIBUTION,
    CONDITION_CLASSES,
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

    def __init__(self, coordinator: AccuWeatherDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)
        # Coordinator data is used also for sensors which don't have units automatically
        # converted, hence the weather entity's native units follow the configured unit
        # system
        if coordinator.hass.config.units is METRIC_SYSTEM:
            self._attr_native_precipitation_unit = UnitOfPrecipitationDepth.MILLIMETERS
            self._attr_native_pressure_unit = UnitOfPressure.HPA
            self._attr_native_temperature_unit = UnitOfTemperature.CELSIUS
            self._attr_native_visibility_unit = UnitOfLength.KILOMETERS
            self._attr_native_wind_speed_unit = UnitOfSpeed.KILOMETERS_PER_HOUR
            self._unit_system = API_METRIC
        else:
            self._unit_system = API_IMPERIAL
            self._attr_native_precipitation_unit = UnitOfPrecipitationDepth.INCHES
            self._attr_native_pressure_unit = UnitOfPressure.INHG
            self._attr_native_temperature_unit = UnitOfTemperature.FAHRENHEIT
            self._attr_native_visibility_unit = UnitOfLength.MILES
            self._attr_native_wind_speed_unit = UnitOfSpeed.MILES_PER_HOUR
        self._attr_unique_id = coordinator.location_key
        self._attr_attribution = ATTRIBUTION
        self._attr_device_info = coordinator.device_info

    @property
    def condition(self) -> str | None:
        """Return the current condition."""
        try:
            return [
                k
                for k, v in CONDITION_CLASSES.items()
                if self.coordinator.data["WeatherIcon"] in v
            ][0]
        except IndexError:
            return None

    @property
    def native_temperature(self) -> float:
        """Return the temperature."""
        return cast(
            float, self.coordinator.data["Temperature"][self._unit_system]["Value"]
        )

    @property
    def native_pressure(self) -> float:
        """Return the pressure."""
        return cast(
            float, self.coordinator.data["Pressure"][self._unit_system]["Value"]
        )

    @property
    def humidity(self) -> int:
        """Return the humidity."""
        return cast(int, self.coordinator.data["RelativeHumidity"])

    @property
    def native_wind_speed(self) -> float:
        """Return the wind speed."""
        return cast(
            float, self.coordinator.data["Wind"]["Speed"][self._unit_system]["Value"]
        )

    @property
    def wind_bearing(self) -> int:
        """Return the wind bearing."""
        return cast(int, self.coordinator.data["Wind"]["Direction"]["Degrees"])

    @property
    def native_visibility(self) -> float:
        """Return the visibility."""
        return cast(
            float, self.coordinator.data["Visibility"][self._unit_system]["Value"]
        )

    @property
    def ozone(self) -> int | None:
        """Return the ozone level."""
        # We only have ozone data for certain locations and only in the forecast data.
        if self.coordinator.forecast and self.coordinator.data[ATTR_FORECAST][0].get(
            "Ozone"
        ):
            return cast(int, self.coordinator.data[ATTR_FORECAST][0]["Ozone"]["Value"])
        return None

    @property
    def forecast(self) -> list[Forecast] | None:
        """Return the forecast array."""
        if not self.coordinator.forecast:
            return None
        # remap keys from library to keys understood by the weather component
        return [
            {
                ATTR_FORECAST_TIME: utc_from_timestamp(item["EpochDate"]).isoformat(),
                ATTR_FORECAST_NATIVE_TEMP: item["TemperatureMax"]["Value"],
                ATTR_FORECAST_NATIVE_TEMP_LOW: item["TemperatureMin"]["Value"],
                ATTR_FORECAST_NATIVE_PRECIPITATION: self._calc_precipitation(item),
                ATTR_FORECAST_PRECIPITATION_PROBABILITY: round(
                    mean(
                        [
                            item["PrecipitationProbabilityDay"],
                            item["PrecipitationProbabilityNight"],
                        ]
                    )
                ),
                ATTR_FORECAST_NATIVE_WIND_SPEED: item["WindDay"]["Speed"]["Value"],
                ATTR_FORECAST_WIND_BEARING: item["WindDay"]["Direction"]["Degrees"],
                ATTR_FORECAST_CONDITION: [
                    k for k, v in CONDITION_CLASSES.items() if item["IconDay"] in v
                ][0],
            }
            for item in self.coordinator.data[ATTR_FORECAST]
        ]

    @staticmethod
    def _calc_precipitation(day: dict[str, Any]) -> float:
        """Return sum of the precipitation."""
        precip_sum = 0
        precip_types = ["Rain", "Snow", "Ice"]
        for precip in precip_types:
            precip_sum = sum(
                [
                    precip_sum,
                    day[f"{precip}Day"]["Value"],
                    day[f"{precip}Night"]["Value"],
                ]
            )
        return round(precip_sum, 1)
