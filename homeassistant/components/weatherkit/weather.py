"""Weather entity for Apple WeatherKit integration."""

from typing import Any, cast

from apple_weatherkit import DataSetType

from homeassistant.components.weather import (
    ATTR_CONDITION_CLOUDY,
    ATTR_CONDITION_EXCEPTIONAL,
    ATTR_CONDITION_FOG,
    ATTR_CONDITION_HAIL,
    ATTR_CONDITION_LIGHTNING,
    ATTR_CONDITION_PARTLYCLOUDY,
    ATTR_CONDITION_POURING,
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SNOWY,
    ATTR_CONDITION_SNOWY_RAINY,
    ATTR_CONDITION_SUNNY,
    ATTR_CONDITION_WINDY,
    Forecast,
    SingleCoordinatorWeatherEntity,
    WeatherEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    UnitOfLength,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTRIBUTION, DOMAIN
from .coordinator import WeatherKitDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add a weather entity from a config_entry."""
    coordinator: WeatherKitDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]

    async_add_entities([WeatherKitWeather(coordinator)])


condition_code_to_hass = {
    "BlowingDust": ATTR_CONDITION_WINDY,
    "Clear": ATTR_CONDITION_SUNNY,
    "Cloudy": ATTR_CONDITION_CLOUDY,
    "Foggy": ATTR_CONDITION_FOG,
    "Haze": ATTR_CONDITION_FOG,
    "MostlyClear": ATTR_CONDITION_SUNNY,
    "MostlyCloudy": ATTR_CONDITION_CLOUDY,
    "PartlyCloudy": ATTR_CONDITION_PARTLYCLOUDY,
    "Smoky": ATTR_CONDITION_FOG,
    "Breezy": ATTR_CONDITION_WINDY,
    "Windy": ATTR_CONDITION_WINDY,
    "Drizzle": ATTR_CONDITION_RAINY,
    "HeavyRain": ATTR_CONDITION_POURING,
    "IsolatedThunderstorms": ATTR_CONDITION_LIGHTNING,
    "Rain": ATTR_CONDITION_RAINY,
    "SunShowers": ATTR_CONDITION_RAINY,
    "ScatteredThunderstorms": ATTR_CONDITION_LIGHTNING,
    "StrongStorms": ATTR_CONDITION_LIGHTNING,
    "Thunderstorms": ATTR_CONDITION_LIGHTNING,
    "Frigid": ATTR_CONDITION_SNOWY,
    "Hail": ATTR_CONDITION_HAIL,
    "Hot": ATTR_CONDITION_SUNNY,
    "Flurries": ATTR_CONDITION_SNOWY,
    "Sleet": ATTR_CONDITION_SNOWY,
    "Snow": ATTR_CONDITION_SNOWY,
    "SunFlurries": ATTR_CONDITION_SNOWY,
    "WintryMix": ATTR_CONDITION_SNOWY,
    "Blizzard": ATTR_CONDITION_SNOWY,
    "BlowingSnow": ATTR_CONDITION_SNOWY,
    "FreezingDrizzle": ATTR_CONDITION_SNOWY_RAINY,
    "FreezingRain": ATTR_CONDITION_SNOWY_RAINY,
    "HeavySnow": ATTR_CONDITION_SNOWY,
    "Hurricane": ATTR_CONDITION_EXCEPTIONAL,
    "TropicalStorm": ATTR_CONDITION_EXCEPTIONAL,
}


def _map_daily_forecast(forecast: dict[str, Any]) -> Forecast:
    return {
        "datetime": forecast["forecastStart"],
        "condition": condition_code_to_hass[forecast["conditionCode"]],
        "native_temperature": forecast["temperatureMax"],
        "native_templow": forecast["temperatureMin"],
        "native_precipitation": forecast["precipitationAmount"],
        "precipitation_probability": forecast["precipitationChance"] * 100,
        "uv_index": forecast["maxUvIndex"],
    }


def _map_hourly_forecast(forecast: dict[str, Any]) -> Forecast:
    return {
        "datetime": forecast["forecastStart"],
        "condition": condition_code_to_hass[forecast["conditionCode"]],
        "native_temperature": forecast["temperature"],
        "native_apparent_temperature": forecast["temperatureApparent"],
        "native_dew_point": forecast.get("temperatureDewPoint"),
        "native_pressure": forecast["pressure"],
        "native_wind_gust_speed": forecast.get("windGust"),
        "native_wind_speed": forecast["windSpeed"],
        "wind_bearing": forecast.get("windDirection"),
        "humidity": forecast["humidity"] * 100,
        "native_precipitation": forecast.get("precipitationAmount"),
        "precipitation_probability": forecast["precipitationChance"] * 100,
        "cloud_coverage": forecast["cloudCover"] * 100,
        "uv_index": forecast["uvIndex"],
    }


class WeatherKitWeather(
    SingleCoordinatorWeatherEntity[WeatherKitDataUpdateCoordinator]
):
    """Weather entity for Apple WeatherKit integration."""

    _attr_attribution = ATTRIBUTION

    _attr_has_entity_name = True
    _attr_name = None

    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_pressure_unit = UnitOfPressure.MBAR
    _attr_native_visibility_unit = UnitOfLength.KILOMETERS
    _attr_native_wind_speed_unit = UnitOfSpeed.KILOMETERS_PER_HOUR

    def __init__(
        self,
        coordinator: WeatherKitDataUpdateCoordinator,
    ) -> None:
        """Initialise the platform with a data instance and site."""
        super().__init__(coordinator)
        config_data = coordinator.config_entry.data
        self._attr_unique_id = (
            f"{config_data[CONF_LATITUDE]}-{config_data[CONF_LONGITUDE]}"
        )
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, self._attr_unique_id)},
            manufacturer="Apple Weather",
        )

    @property
    def supported_features(self) -> WeatherEntityFeature:
        """Determine supported features based on available data sets reported by WeatherKit."""
        features = WeatherEntityFeature(0)

        if not self.coordinator.supported_data_sets:
            return features

        if DataSetType.DAILY_FORECAST in self.coordinator.supported_data_sets:
            features |= WeatherEntityFeature.FORECAST_DAILY
        if DataSetType.HOURLY_FORECAST in self.coordinator.supported_data_sets:
            features |= WeatherEntityFeature.FORECAST_HOURLY
        return features

    @property
    def data(self) -> dict[str, Any]:
        """Return coordinator data."""
        return self.coordinator.data

    @property
    def current_weather(self) -> dict[str, Any]:
        """Return current weather data."""
        return self.data["currentWeather"]

    @property
    def condition(self) -> str | None:
        """Return the current condition."""
        condition_code = cast(str, self.current_weather.get("conditionCode"))
        condition = condition_code_to_hass[condition_code]

        if condition == "sunny" and self.current_weather.get("daylight") is False:
            condition = "clear-night"

        return condition

    @property
    def native_temperature(self) -> float | None:
        """Return the current temperature."""
        return self.current_weather.get("temperature")

    @property
    def native_apparent_temperature(self) -> float | None:
        """Return the current apparent_temperature."""
        return self.current_weather.get("temperatureApparent")

    @property
    def native_dew_point(self) -> float | None:
        """Return the current dew_point."""
        return self.current_weather.get("temperatureDewPoint")

    @property
    def native_pressure(self) -> float | None:
        """Return the current pressure."""
        return self.current_weather.get("pressure")

    @property
    def humidity(self) -> float | None:
        """Return the current humidity."""
        return cast(float, self.current_weather.get("humidity")) * 100

    @property
    def cloud_coverage(self) -> float | None:
        """Return the current cloud_coverage."""
        return cast(float, self.current_weather.get("cloudCover")) * 100

    @property
    def uv_index(self) -> float | None:
        """Return the current uv_index."""
        return self.current_weather.get("uvIndex")

    @property
    def native_visibility(self) -> float | None:
        """Return the current visibility."""
        return cast(float, self.current_weather.get("visibility")) / 1000

    @property
    def native_wind_gust_speed(self) -> float | None:
        """Return the current wind_gust_speed."""
        return self.current_weather.get("windGust")

    @property
    def native_wind_speed(self) -> float | None:
        """Return the current wind_speed."""
        return self.current_weather.get("windSpeed")

    @property
    def wind_bearing(self) -> float | None:
        """Return the current wind_bearing."""
        return self.current_weather.get("windDirection")

    @callback
    def _async_forecast_daily(self) -> list[Forecast] | None:
        """Return the daily forecast."""
        daily_forecast = self.data.get("forecastDaily")
        if not daily_forecast:
            return None

        forecast = daily_forecast.get("days")
        return [_map_daily_forecast(f) for f in forecast]

    @callback
    def _async_forecast_hourly(self) -> list[Forecast] | None:
        """Return the hourly forecast."""
        hourly_forecast = self.data.get("forecastHourly")
        if not hourly_forecast:
            return None

        forecast = hourly_forecast.get("hours")
        return [_map_hourly_forecast(f) for f in forecast]
