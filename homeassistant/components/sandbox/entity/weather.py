"""Sandbox proxy for weather entities."""

from __future__ import annotations

from homeassistant.components.weather import Forecast, WeatherEntity, WeatherEntityFeature

from . import SandboxEntityDescription, SandboxEntityManager, SandboxProxyEntity


class SandboxWeatherEntity(SandboxProxyEntity, WeatherEntity):
    """Proxy for a weather entity in a sandbox."""

    def __init__(
        self,
        description: SandboxEntityDescription,
        manager: SandboxEntityManager,
    ) -> None:
        """Initialize the proxy weather entity."""
        super().__init__(description, manager)
        self._attr_supported_features = WeatherEntityFeature(
            description.supported_features
        )
        caps = description.capabilities
        if temp_unit := caps.get("native_temperature_unit"):
            self._attr_native_temperature_unit = temp_unit
        if pressure_unit := caps.get("native_pressure_unit"):
            self._attr_native_pressure_unit = pressure_unit
        if wind_speed_unit := caps.get("native_wind_speed_unit"):
            self._attr_native_wind_speed_unit = wind_speed_unit
        if visibility_unit := caps.get("native_visibility_unit"):
            self._attr_native_visibility_unit = visibility_unit
        if precipitation_unit := caps.get("native_precipitation_unit"):
            self._attr_native_precipitation_unit = precipitation_unit

    @property
    def condition(self) -> str | None:
        """Return the weather condition."""
        return self._state_cache.get("condition")

    @property
    def native_temperature(self) -> float | None:
        """Return the temperature."""
        return self._state_cache.get("native_temperature")

    @property
    def native_apparent_temperature(self) -> float | None:
        """Return the apparent temperature."""
        return self._state_cache.get("native_apparent_temperature")

    @property
    def native_pressure(self) -> float | None:
        """Return the pressure."""
        return self._state_cache.get("native_pressure")

    @property
    def humidity(self) -> float | None:
        """Return the humidity."""
        return self._state_cache.get("humidity")

    @property
    def native_wind_speed(self) -> float | None:
        """Return the wind speed."""
        return self._state_cache.get("native_wind_speed")

    @property
    def wind_bearing(self) -> float | str | None:
        """Return the wind bearing."""
        return self._state_cache.get("wind_bearing")

    @property
    def native_visibility(self) -> float | None:
        """Return the visibility."""
        return self._state_cache.get("native_visibility")

    async def async_forecast_daily(self) -> list[Forecast] | None:
        """Forward forecast_daily to sandbox."""
        return await self._forward_method("async_forecast_daily")

    async def async_forecast_hourly(self) -> list[Forecast] | None:
        """Forward forecast_hourly to sandbox."""
        return await self._forward_method("async_forecast_hourly")

    async def async_forecast_twice_daily(self) -> list[Forecast] | None:
        """Forward forecast_twice_daily to sandbox."""
        return await self._forward_method("async_forecast_twice_daily")
