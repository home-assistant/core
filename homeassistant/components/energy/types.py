"""Types for the energy platform."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol, TypedDict

from homeassistant.core import HomeAssistant


class SolarForecastType(TypedDict):
    """Return value for solar forecast."""

    wh_hours: dict[str, float | int]


type GetSolarForecastType = Callable[
    [HomeAssistant, str], Awaitable[SolarForecastType | None]
]


class EnergyPlatform(Protocol):
    """Represents the methods we expect on the energy platforms."""

    @staticmethod
    async def async_get_solar_forecast(
        hass: HomeAssistant, config_entry_id: str
    ) -> SolarForecastType | None:
        """Get forecast for solar production for specific config entry ID."""
