"""Support for IRM KMI weather."""

import logging

from homeassistant.components.weather import (
    Forecast,
    WeatherEntity,
    WeatherEntityFeature,
)
from homeassistant.const import (
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import IrmKmiConfigEntry
from .entity import IrmKmiBaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: IrmKmiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the weather entry."""
    async_add_entities([IrmKmiWeather(entry)])


class IrmKmiWeather(WeatherEntity, IrmKmiBaseEntity):
    """Weather entity for IRM KMI weather."""

    _attr_has_entity_name = True

    def __init__(self, entry: IrmKmiConfigEntry) -> None:
        """Create a new instance of the weather entity from a configuration entry."""
        WeatherEntity.__init__(self)
        IrmKmiBaseEntity.__init__(self, entry, "Forecast")
        self._name = entry.title
        self._attr_unique_id = entry.entry_id

    @property
    def supported_features(self) -> WeatherEntityFeature:
        """Flag supported features."""
        features = WeatherEntityFeature(0)
        features |= WeatherEntityFeature.FORECAST_DAILY
        features |= WeatherEntityFeature.FORECAST_TWICE_DAILY
        features |= WeatherEntityFeature.FORECAST_HOURLY
        return features

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def condition(self) -> str | None:
        """Return the current condition."""
        return self.coordinator.data.get("current_weather", {}).get("condition")

    @property
    def native_temperature(self) -> float | None:
        """Return the temperature in native units."""
        return self.coordinator.data.get("current_weather", {}).get("temperature")

    @property
    def native_temperature_unit(self) -> str | None:
        """Return the native unit of measurement for temperature."""
        return UnitOfTemperature.CELSIUS

    @property
    def native_wind_speed_unit(self) -> str | None:
        """Return the native unit of measurement for wind speed."""
        return UnitOfSpeed.KILOMETERS_PER_HOUR

    @property
    def native_wind_speed(self) -> float | None:
        """Return the wind speed in native units."""
        return self.coordinator.data.get("current_weather", {}).get("wind_speed")

    @property
    def native_wind_gust_speed(self) -> float | None:
        """Return the wind gust speed in native units."""
        return self.coordinator.data.get("current_weather", {}).get("wind_gust_speed")

    @property
    def wind_bearing(self) -> float | str | None:
        """Return the wind bearing."""
        return self.coordinator.data.get("current_weather", {}).get("wind_bearing")

    @property
    def native_precipitation_unit(self) -> str | None:
        """Return the native unit of measurement for accumulated precipitation."""
        return UnitOfPrecipitationDepth.MILLIMETERS

    @property
    def native_pressure(self) -> float | None:
        """Return the pressure in native units."""
        return self.coordinator.data.get("current_weather", {}).get("pressure")

    @property
    def native_pressure_unit(self) -> str | None:
        """Return the native unit of measurement for pressure."""
        return UnitOfPressure.HPA

    @property
    def uv_index(self) -> float | None:
        """Return the UV index."""
        return self.coordinator.data.get("current_weather", {}).get("uv_index")

    async def async_forecast_twice_daily(self) -> list[Forecast] | None:
        """Return the daily forecast in native units."""
        return self.coordinator.data.get("daily_forecast")

    async def async_forecast_daily(self) -> list[Forecast] | None:
        """Return the daily forecast in native units."""
        return self.daily_forecast()

    async def async_forecast_hourly(self) -> list[Forecast] | None:
        """Return the hourly forecast in native units."""
        return self.coordinator.data.get("hourly_forecast")

    def daily_forecast(self) -> list[Forecast] | None:
        """Return the daily forecast in native units."""
        data: list[Forecast] = self.coordinator.data.get("daily_forecast", [])
        if not isinstance(data, list):
            return None

        # The data in daily_forecast might contain nighttime forecast.
        # The following handle the lowest temperature attribute to be displayed correctly.
        if (
            len(data) > 1
            and not data[0].get("is_daytime")
            and data[1].get("native_templow") is None
        ):
            data[1]["native_templow"] = data[0].get("native_templow")
            if (
                data[1]["native_templow"] is not None
                and data[1]["native_temperature"] is not None
                and data[1]["native_templow"] > data[1]["native_temperature"]
            ):
                (data[1]["native_templow"], data[1]["native_temperature"]) = (
                    data[1]["native_temperature"],
                    data[1]["native_templow"],
                )

        if len(data) > 0 and not data[0].get("is_daytime"):
            return data

        if (
            len(data) > 1
            and data[0].get("native_templow") is None
            and not data[1].get("is_daytime")
        ):
            data[0]["native_templow"] = data[1].get("native_templow")
            if (
                data[0]["native_templow"] is not None
                and data[0]["native_temperature"] is not None
                and data[0]["native_templow"] > data[0]["native_temperature"]
            ):
                (data[0]["native_templow"], data[0]["native_temperature"]) = (
                    data[0]["native_temperature"],
                    data[0]["native_templow"],
                )

        return [f for f in data if f.get("is_daytime")]
