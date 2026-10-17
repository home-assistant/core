"""Sandbox proxy for ``weather`` entities."""

from typing import override

from homeassistant.components.weather import (
    ATTR_WEATHER_HUMIDITY,
    ATTR_WEATHER_TEMPERATURE,
    ATTR_WEATHER_TEMPERATURE_UNIT,
    ATTR_WEATHER_WIND_BEARING,
    ATTR_WEATHER_WIND_SPEED,
    ATTR_WEATHER_WIND_SPEED_UNIT,
    Forecast,
    WeatherEntity,
    WeatherEntityFeature,
)

from . import SandboxProxyEntity


# pylint: disable-next=home-assistant-enforce-class-module
class SandboxWeatherEntity(SandboxProxyEntity, WeatherEntity):
    """Proxy for a ``weather`` entity in a sandbox."""

    _features_flag = WeatherEntityFeature

    @property
    @override
    def condition(self) -> str | None:
        """Return the cached weather condition."""
        value = self._state_cache.get("state")
        if value in (None, "unavailable", "unknown"):
            return None
        return value

    @property
    @override
    def native_temperature(self) -> float | None:
        """Return the cached temperature."""
        value = self._state_cache.get(ATTR_WEATHER_TEMPERATURE)
        return None if value is None else float(value)

    @property
    @override
    def native_temperature_unit(self) -> str | None:
        """Return the cached temperature unit."""
        return self._state_cache.get(ATTR_WEATHER_TEMPERATURE_UNIT)

    @property
    @override
    def humidity(self) -> float | None:
        """Return the cached humidity."""
        value = self._state_cache.get(ATTR_WEATHER_HUMIDITY)
        return None if value is None else float(value)

    @property
    @override
    def native_wind_speed(self) -> float | None:
        """Return the cached wind speed."""
        value = self._state_cache.get(ATTR_WEATHER_WIND_SPEED)
        return None if value is None else float(value)

    @property
    @override
    def native_wind_speed_unit(self) -> str | None:
        """Return the cached wind speed unit."""
        return self._state_cache.get(ATTR_WEATHER_WIND_SPEED_UNIT)

    @property
    @override
    def wind_bearing(self) -> float | str | None:
        """Return the cached wind bearing."""
        return self._state_cache.get(ATTR_WEATHER_WIND_BEARING)

    async def _async_forecast(self, forecast_type: str) -> list[Forecast]:
        """Forward a forecast query as the ``weather.get_forecasts`` service."""
        response = await self._call_service(
            "get_forecasts", return_response=True, type=forecast_type
        )
        entity_response = response.get(self.description.sandbox_entity_id, {})
        return entity_response.get("forecast", [])

    @override
    async def async_forecast_daily(self) -> list[Forecast] | None:
        """Return the daily forecast via ``weather.get_forecasts``."""
        return await self._async_forecast("daily")

    @override
    async def async_forecast_hourly(self) -> list[Forecast] | None:
        """Return the hourly forecast via ``weather.get_forecasts``."""
        return await self._async_forecast("hourly")

    @override
    async def async_forecast_twice_daily(self) -> list[Forecast] | None:
        """Return the twice-daily forecast via ``weather.get_forecasts``."""
        return await self._async_forecast("twice_daily")
