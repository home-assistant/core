"""Sandbox proxy for ``weather`` entities."""

from typing import TYPE_CHECKING

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

from . import SandboxProxyEntity, raise_not_proxied

if TYPE_CHECKING:
    from ..bridge import SandboxBridge, SandboxEntityDescription


# pylint: disable-next=home-assistant-enforce-class-module
class SandboxWeatherEntity(SandboxProxyEntity, WeatherEntity):
    """Proxy for a ``weather`` entity in a sandbox.

    The proxy mirrors the condition + instantaneous attributes. Forecasts are a
    server-side query (the ``weather.get_forecasts`` service and the
    ``weather/subscribe_forecast`` WS command call ``async_forecast_*`` on the
    entity) that the entity-method bridge can't express yet, so they raise
    rather than silently returning an empty forecast. See
    ``sandbox/docs/query-shaped-rpcs.md``.
    """

    def __init__(
        self,
        bridge: SandboxBridge,
        description: SandboxEntityDescription,
    ) -> None:
        """Wrap ``supported_features`` as ``WeatherEntityFeature``."""
        super().__init__(bridge, description)
        self._attr_supported_features = WeatherEntityFeature(
            description.supported_features or 0
        )

    @property
    def condition(self) -> str | None:
        """Return the cached weather condition."""
        value = self._state_cache.get("state")
        if value in (None, "unavailable", "unknown"):
            return None
        return value

    @property
    def native_temperature(self) -> float | None:
        """Return the cached temperature."""
        value = self._state_cache.get(ATTR_WEATHER_TEMPERATURE)
        return None if value is None else float(value)

    @property
    def native_temperature_unit(self) -> str | None:
        """Return the cached temperature unit."""
        return self._state_cache.get(ATTR_WEATHER_TEMPERATURE_UNIT)

    @property
    def humidity(self) -> float | None:
        """Return the cached humidity."""
        value = self._state_cache.get(ATTR_WEATHER_HUMIDITY)
        return None if value is None else float(value)

    @property
    def native_wind_speed(self) -> float | None:
        """Return the cached wind speed."""
        value = self._state_cache.get(ATTR_WEATHER_WIND_SPEED)
        return None if value is None else float(value)

    @property
    def native_wind_speed_unit(self) -> str | None:
        """Return the cached wind speed unit."""
        return self._state_cache.get(ATTR_WEATHER_WIND_SPEED_UNIT)

    @property
    def wind_bearing(self) -> float | str | None:
        """Return the cached wind bearing."""
        return self._state_cache.get(ATTR_WEATHER_WIND_BEARING)

    async def async_forecast_daily(self) -> list[Forecast] | None:
        """Raise — forecasts are a server-side query, not yet proxied."""
        raise_not_proxied("Fetching the daily weather forecast")

    async def async_forecast_hourly(self) -> list[Forecast] | None:
        """Raise — forecasts are a server-side query, not yet proxied."""
        raise_not_proxied("Fetching the hourly weather forecast")

    async def async_forecast_twice_daily(self) -> list[Forecast] | None:
        """Raise — forecasts are a server-side query, not yet proxied."""
        raise_not_proxied("Fetching the twice-daily weather forecast")
