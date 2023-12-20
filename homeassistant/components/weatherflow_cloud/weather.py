"""Support for WeatherFlow Forecast weather service."""
from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from weatherflow4py.models.unified import WeatherFlowData

from homeassistant.components.weather import (
    Forecast,
    SingleCoordinatorWeatherEntity,
    WeatherEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.dt import utc_from_timestamp
from homeassistant.util.unit_system import METRIC_SYSTEM

from .const import (
    ATTR_ATTRIBUTION,
    CONF_FIRMWARE_REVISION,
    CONF_STATION_ID,
    DEFAULT_NAME,
    DOMAIN,
    MANUFACTURER,
    MODEL,
)
from .coordinator import WeatherFlowCloudDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add a weather entity from a config_entry."""
    coordinator: WeatherFlowCloudDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]


    # Figure out how many entries we have before doing anything

    entities = []
    is_metric = hass.config.units is METRIC_SYSTEM


    for station_id,data in coordinator.data.items():
        entities.append(WeatherFlowWeather(coordinator, config_entry.data, station_id=station_id, is_metric=is_metric))


    async_add_entities(entities)



class WeatherFlowWeather(
    SingleCoordinatorWeatherEntity[WeatherFlowCloudDataUpdateCoordinator]
):
    """Implementation of a WeatherFlow weather condition."""

    _attr_attribution = ATTR_ATTRIBUTION
    _attr_has_entity_name = True
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_precipitation_unit = UnitOfPrecipitationDepth.MILLIMETERS
    _attr_native_pressure_unit = UnitOfPressure.HPA
    _attr_native_wind_speed_unit = UnitOfSpeed.METERS_PER_SECOND
    _attr_supported_features = (
        WeatherEntityFeature.FORECAST_DAILY | WeatherEntityFeature.FORECAST_HOURLY
    )

    def __init__(
        self,
        coordinator: WeatherFlowCloudDataUpdateCoordinator,
        config: MappingProxyType[str, Any],
        station_id: int,
        is_metric: bool,
    ) -> None:
        """Initialise the platform with a data instance and station."""
        super().__init__(coordinator)

        self.station_id = station_id
        self._attr_unique_id = f"weatherflow_forecast_{station_id}"
        self._attr_name = self.local_data.station.name

        # which device do we want:
        outdoor_device = [d for d in self.local_data.station.devices if d.device_type == "ST"][0]

        self._config = config
        self._is_metric = is_metric
        self._hourly = True
        # self._attr_entity_registry_enabled_default = not hourly
        self._attr_device_info = DeviceInfo(
            name="Forecast",
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN,outdoor_device.serial_number)},  # type: ignore[arg-type]
            manufacturer=MANUFACTURER,
            configuration_url=f"https://tempestwx.com/station/{station_id}/grid",
            serial_number=outdoor_device.serial_number,
            sw_version=outdoor_device.firmware_revision,
            hw_version=outdoor_device.hardware_revision,

        )

    @property
    def local_data(self) -> WeatherFlowData:
        return self.coordinator.data[self.station_id]

    @property
    def condition(self) -> str | None:
        """Return current condition - required property."""
        return self.local_data.weather.current_conditions.icon.value

    @property
    def native_temperature(self) -> float | None:
        """Return the temperature."""
        return self.local_data.weather.current_conditions.air_temperature

    # @property
    # def native_temperature_unit(self) -> str | None:
    #     return self.local_data.weather.units.units_temp


    # @property
    # def native_pressure(self) -> float | None:
    #     """Return the pressure."""
    #
    #     return self.coordinator.weather.current_weather_data.pressure
    #
    # @property
    # def humidity(self) -> float | None:
    #     """Return the humidity."""
    #
    #     return self.coordinator.weather.current_weather_data.humidity
    #
    # @property
    # def native_wind_speed(self) -> float | None:
    #     """Return the wind speed."""
    #     return self.coordinator.weather.current_weather_data.wind_speed
    #
    # @property
    # def wind_bearing(self) -> float | str | None:
    #     """Return the wind direction."""
    #     return self.coordinator.weather.current_weather_data.wind_bearing
    #
    # @property
    # def native_wind_gust_speed(self) -> float | None:
    #     """Return the wind gust speed in native units."""
    #     return self.coordinator.weather.current_weather_data.wind_gust_speed
    #
    # @property
    # def native_dew_point(self) -> float | None:
    #     """Return the dew point."""
    #     return self.coordinator.weather.current_weather_data.dew_point
    #
    # def _forecast(self, hourly: bool) -> list[Forecast] | None:
    #     """Return the forecast array."""
    #     ha_forecast: list[Forecast] = []
    #
    #     if hourly:
    #         for item in self.coordinator.weather.hourly_forecast:
    #             condition = item.icon
    #             datetime = utc_from_timestamp(item.timestamp).isoformat()
    #             humidity = item.humidity
    #             precipitation_probability = item.precipitation_probability
    #             native_precipitation = item.precipitation
    #             native_pressure = item.pressure
    #             native_temperature = item.temperature
    #             native_apparent_temperature = item.apparent_temperature
    #             wind_bearing = item.wind_bearing
    #             native_wind_gust_speed = item.wind_gust_speed
    #             native_wind_speed = item.wind_speed
    #             uv_index = item.uv_index
    #
    #             ha_item: Forecast = {
    #                 "condition": condition,
    #                 "datetime": datetime,
    #                 "humidity": humidity,
    #                 "precipitation_probability": precipitation_probability,
    #                 "native_precipitation": native_precipitation,
    #                 "native_pressure": native_pressure,
    #                 "native_temperature": native_temperature,
    #                 "native_apparent_temperature": native_apparent_temperature,
    #                 "wind_bearing": wind_bearing,
    #                 "native_wind_gust_speed": native_wind_gust_speed,
    #                 "native_wind_speed": native_wind_speed,
    #                 "uv_index": uv_index,
    #             }
    #             ha_forecast.append(ha_item)
    #     else:
    #         for item in self.coordinator.weather.daily_forecast:
    #             condition = item.icon
    #             datetime = utc_from_timestamp(item.timestamp).isoformat()
    #             precipitation_probability = item.precipitation_probability
    #             native_temperature = item.temperature
    #             native_templow = item.temp_low
    #             native_precipitation = item.precipitation
    #             wind_bearing = int(item.wind_bearing)
    #             native_wind_speed = item.wind_speed
    #
    #             ha_item = {
    #                 "condition": condition,
    #                 "datetime": datetime,
    #                 "precipitation_probability": precipitation_probability,
    #                 "native_precipitation": native_precipitation,
    #                 "native_temperature": native_temperature,
    #                 "native_templow": native_templow,
    #                 "wind_bearing": wind_bearing,
    #                 "native_wind_speed": native_wind_speed,
    #             }
    #
    #             ha_forecast.append(ha_item)
    #
    #     return ha_forecast

    @callback
    def _async_forecast_daily(self) -> list[Forecast] | None:
        """Return the daily forecast in native units."""
        daily = self.local_data.weather.forecast.daily

        return self._forecast(False)
    #
    # @callback
    # def _async_forecast_hourly(self) -> list[Forecast] | None:
    #     """Return the hourly forecast in native units."""
    #     return self._forecast(True)
