"""Support for the OpenWeatherMap (OWM) service."""

from __future__ import annotations

from homeassistant.components.weather import (
    Forecast,
    SingleCoordinatorWeatherEntity,
    WeatherEntityFeature,
)
from homeassistant.const import (
    UnitOfLength,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, SupportsResponse, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_platform
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import OpenweathermapConfigEntry
from .const import (
    ATTR_API_CLOUDS,
    ATTR_API_CONDITION,
    ATTR_API_CURRENT,
    ATTR_API_DAILY_FORECAST,
    ATTR_API_DEW_POINT,
    ATTR_API_FEELS_LIKE_TEMPERATURE,
    ATTR_API_HOURLY_FORECAST,
    ATTR_API_HUMIDITY,
    ATTR_API_MINUTE_FORECAST,
    ATTR_API_PRESSURE,
    ATTR_API_TEMPERATURE,
    ATTR_API_VISIBILITY_DISTANCE,
    ATTR_API_WIND_BEARING,
    ATTR_API_WIND_GUST,
    ATTR_API_WIND_SPEED,
    ATTRIBUTION,
    DEFAULT_NAME,
    DOMAIN,
    MANUFACTURER,
    OWM_MODE_FREE_FORECAST,
    OWM_MODE_V30,
)
from .coordinator import WeatherUpdateCoordinator

SERVICE_GET_MINUTE_FORECAST = "get_minute_forecast"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: OpenweathermapConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up OpenWeatherMap weather entity based on a config entry."""
    domain_data = config_entry.runtime_data
    name = domain_data.name
    mode = domain_data.mode
    weather_coordinator = domain_data.coordinator

    unique_id = f"{config_entry.unique_id}"
    owm_weather = OpenWeatherMapWeather(name, unique_id, mode, weather_coordinator)

    async_add_entities([owm_weather], False)

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        name=SERVICE_GET_MINUTE_FORECAST,
        schema=None,
        func="async_get_minute_forecast",
        supports_response=SupportsResponse.ONLY,
    )


class OpenWeatherMapWeather(SingleCoordinatorWeatherEntity[WeatherUpdateCoordinator]):
    """Implementation of an OpenWeatherMap sensor."""

    _attr_attribution = ATTRIBUTION
    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_name = None

    _attr_native_precipitation_unit = UnitOfPrecipitationDepth.MILLIMETERS
    _attr_native_pressure_unit = UnitOfPressure.HPA
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_wind_speed_unit = UnitOfSpeed.METERS_PER_SECOND
    _attr_native_visibility_unit = UnitOfLength.METERS

    def __init__(
        self,
        name: str,
        unique_id: str,
        mode: str,
        weather_coordinator: WeatherUpdateCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(weather_coordinator)
        self._attr_unique_id = unique_id
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, unique_id)},
            manufacturer=MANUFACTURER,
            name=name,
        )
        self.mode = mode

        if mode == OWM_MODE_V30:
            self._attr_supported_features = (
                WeatherEntityFeature.FORECAST_DAILY
                | WeatherEntityFeature.FORECAST_HOURLY
            )
        elif mode == OWM_MODE_FREE_FORECAST:
            self._attr_supported_features = WeatherEntityFeature.FORECAST_HOURLY

    async def async_get_minute_forecast(self) -> dict[str, list[dict]] | dict:
        """Return Minute forecast."""

        if self.mode == OWM_MODE_V30:
            return self.coordinator.data[ATTR_API_MINUTE_FORECAST]
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="service_minute_forecast_mode",
            translation_placeholders={"name": DEFAULT_NAME},
        )

    @property
    def condition(self) -> str | None:
        """Return the current condition."""
        return self.coordinator.data[ATTR_API_CURRENT].get(ATTR_API_CONDITION)

    @property
    def cloud_coverage(self) -> float | None:
        """Return the Cloud coverage in %."""
        return self.coordinator.data[ATTR_API_CURRENT].get(ATTR_API_CLOUDS)

    @property
    def native_apparent_temperature(self) -> float | None:
        """Return the apparent temperature."""
        return self.coordinator.data[ATTR_API_CURRENT].get(
            ATTR_API_FEELS_LIKE_TEMPERATURE
        )

    @property
    def native_temperature(self) -> float | None:
        """Return the temperature."""
        return self.coordinator.data[ATTR_API_CURRENT].get(ATTR_API_TEMPERATURE)

    @property
    def native_pressure(self) -> float | None:
        """Return the pressure."""
        return self.coordinator.data[ATTR_API_CURRENT].get(ATTR_API_PRESSURE)

    @property
    def humidity(self) -> float | None:
        """Return the humidity."""
        return self.coordinator.data[ATTR_API_CURRENT].get(ATTR_API_HUMIDITY)

    @property
    def native_dew_point(self) -> float | None:
        """Return the dew point."""
        return self.coordinator.data[ATTR_API_CURRENT].get(ATTR_API_DEW_POINT)

    @property
    def native_wind_gust_speed(self) -> float | None:
        """Return the wind gust speed."""
        return self.coordinator.data[ATTR_API_CURRENT].get(ATTR_API_WIND_GUST)

    @property
    def native_wind_speed(self) -> float | None:
        """Return the wind speed."""
        return self.coordinator.data[ATTR_API_CURRENT].get(ATTR_API_WIND_SPEED)

    @property
    def wind_bearing(self) -> float | str | None:
        """Return the wind bearing."""
        return self.coordinator.data[ATTR_API_CURRENT].get(ATTR_API_WIND_BEARING)

    @property
    def visibility(self) -> float | str | None:
        """Return visibility."""
        return self.coordinator.data[ATTR_API_CURRENT].get(ATTR_API_VISIBILITY_DISTANCE)

    @callback
    def _async_forecast_daily(self) -> list[Forecast] | None:
        """Return the daily forecast in native units."""
        return self.coordinator.data[ATTR_API_DAILY_FORECAST]

    @callback
    def _async_forecast_hourly(self) -> list[Forecast] | None:
        """Return the hourly forecast in native units."""
        return self.coordinator.data[ATTR_API_HOURLY_FORECAST]
