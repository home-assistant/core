"""Support for Open-Meteo weather."""
from __future__ import annotations

from types import MappingProxyType

from open_meteo import DailyForecast, Forecast as OpenMeteoForecast, HourlyForecast

from homeassistant.components.weather import Forecast, WeatherEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPrecipitationDepth, UnitOfSpeed, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN, WMO_TO_HA_CONDITION_MAP


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Open-Meteo weather entity based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            OpenMeteoWeatherEntity(entry=entry, coordinator=coordinator, hourly=False),
            OpenMeteoWeatherEntity(entry=entry, coordinator=coordinator, hourly=True),
        ]
    )


class OpenMeteoWeatherEntity(
    CoordinatorEntity[DataUpdateCoordinator[OpenMeteoForecast]], WeatherEntity
):
    """Defines an Open-Meteo weather entity."""

    _attr_has_entity_name = True
    _attr_native_precipitation_unit = UnitOfPrecipitationDepth.MILLIMETERS
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_wind_speed_unit = UnitOfSpeed.KILOMETERS_PER_HOUR

    def __init__(
        self,
        *,
        entry: ConfigEntry,
        coordinator: DataUpdateCoordinator[OpenMeteoForecast],
        hourly: bool,
    ) -> None:
        """Initialize Open-Meteo weather entity."""
        super().__init__(coordinator=coordinator)
        self.entry_id = entry.entry_id
        self._config = MappingProxyType(entry.data)
        self._hourly = hourly
        self._attr_name = "Hourly" if hourly else "Daily"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="Open-Meteo",
            name=entry.title,
            configuration_url="https://open-meteo.com/",
        )

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        name_appendix = ""
        if self._hourly:
            name_appendix = "-hourly"
        unique_id = f"{self.entry_id}{name_appendix}"
        return unique_id

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return not self._hourly

    @property
    def condition(self) -> str | None:
        """Return the current condition."""
        if not self.coordinator.data.current_weather:
            return None
        return WMO_TO_HA_CONDITION_MAP.get(
            self.coordinator.data.current_weather.weather_code
        )

    @property
    def native_temperature(self) -> float | None:
        """Return the platform temperature."""
        if not self.coordinator.data.current_weather:
            return None
        return self.coordinator.data.current_weather.temperature

    @property
    def native_wind_speed(self) -> float | None:
        """Return the wind speed."""
        if not self.coordinator.data.current_weather:
            return None
        return self.coordinator.data.current_weather.wind_speed

    @property
    def wind_bearing(self) -> float | str | None:
        """Return the wind bearing."""
        if not self.coordinator.data.current_weather:
            return None
        return self.coordinator.data.current_weather.wind_direction

    @property
    def forecast(self) -> list[Forecast] | None:
        """Return the forecast in native units."""
        forecasts: list[Forecast] = []

        if self._hourly:
            if self.coordinator.data.hourly is None:
                return None
            hourly_fc: HourlyForecast = self.coordinator.data.hourly

            for index, time in enumerate(hourly_fc.time):
                forecast = Forecast(
                    datetime=time.isoformat(),
                )

                if hourly_fc.weather_code is not None:
                    forecast["condition"] = WMO_TO_HA_CONDITION_MAP.get(
                        hourly_fc.weather_code[index]
                    )

                if hourly_fc.precipitation is not None:
                    forecast["native_precipitation"] = hourly_fc.precipitation[index]

                if hourly_fc.temperature_2m is not None:
                    forecast["native_temperature"] = hourly_fc.temperature_2m[index]

                if hourly_fc.wind_speed_10m is not None:
                    forecast["native_wind_speed"] = hourly_fc.wind_speed_10m[index]

                if hourly_fc.wind_direction_10m is not None:
                    forecast["wind_bearing"] = hourly_fc.wind_direction_10m[index]

                forecasts.append(forecast)
        else:
            if self.coordinator.data.daily is None:
                return None
            daily_fc: DailyForecast = self.coordinator.data.daily

            for index, time in enumerate(daily_fc.time):  # type: ignore[assignment]
                forecast = Forecast(
                    datetime=time.isoformat(),
                )
                if daily_fc.weathercode is not None:
                    forecast["condition"] = WMO_TO_HA_CONDITION_MAP.get(
                        daily_fc.weathercode[index]
                    )

                if daily_fc.precipitation_sum is not None:
                    forecast["native_precipitation"] = daily_fc.precipitation_sum[index]

                if daily_fc.temperature_2m_max is not None:
                    forecast["native_temperature"] = daily_fc.temperature_2m_max[index]

                if daily_fc.temperature_2m_min is not None:
                    forecast["native_templow"] = daily_fc.temperature_2m_min[index]

                if daily_fc.wind_direction_10m_dominant is not None:
                    forecast["wind_bearing"] = daily_fc.wind_direction_10m_dominant[
                        index
                    ]

                if daily_fc.wind_speed_10m_max is not None:
                    forecast["native_wind_speed"] = daily_fc.wind_speed_10m_max[index]

                forecasts.append(forecast)

        return forecasts
