"""Energy data."""
from __future__ import annotations

from typing import Optional, TypedDict, cast

import voluptuous as vol

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import singleton, storage

from .const import DOMAIN

STORAGE_VERSION = 1
STORAGE_KEY = DOMAIN


HOME_CONSUMPTION_SCHEMA = vol.Schema(
    {
        vol.Required("stat_consumption"): str,
        vol.Required("stat_cost"): vol.Any(None, str),
        vol.Required("cost_adjustment_day"): vol.Coerce(float),
    }
)
DEVICE_CONSUMPTION_SCHEMA = vol.Schema(
    {
        vol.Required("stat_consumption"): str,
    }
)
PRODUCTION_SCHEMA = vol.Schema(
    {
        vol.Required("type"): vol.In(("solar", "wind")),
        vol.Required("stat_production"): str,
        vol.Required("stat_return_to_grid"): vol.Any(str, None),
        vol.Required("stat_predicted_production"): vol.Any(str, None),
    }
)


@singleton.singleton(DOMAIN)
async def async_get_manager(hass: HomeAssistant) -> EnergyManager:
    """Return an initialized data manager."""
    manager = EnergyManager(hass)
    await manager.async_initialize()
    return manager


class EnergyHomeConsumption(TypedDict):
    """Dictionary holding the source of grid energy consumption."""

    # This is an ever increasing value
    stat_consumption: str
    entity_consumption: str | None

    # this is an ever increasing value
    stat_cost: str | None

    entity_energy_price: str | None
    cost_adjustment_day: float


class EnergyDeviceConsumption(TypedDict):
    """Dictionary holding the source of individual device consumption."""

    # This is an ever increasing value
    stat_consumption: str


class EnergyProduction(TypedDict):
    """Dictionary holding the source of energy production."""

    type: str  # "solar" | "wind"

    stat_production: str
    stat_return_to_grid: str | None
    stat_predicted_production: str | None


class EnergyPreferences(TypedDict):
    """Dictionary holding the energy data."""

    currency: str
    home_consumption: list[EnergyHomeConsumption]
    device_consumption: list[EnergyDeviceConsumption]
    production: list[EnergyProduction]


class EnergyPreferencesUpdate(EnergyPreferences, total=False):
    """all types optional."""


class EnergyManager:
    """Manage the instance energy prefs."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize energy manager."""
        self._hass = hass
        self._store = storage.Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self.data: EnergyPreferences | None = None

    async def async_initialize(self) -> None:
        """Initialize the energy integration."""
        self.data = cast(Optional[EnergyPreferences], await self._store.async_load())

    @staticmethod
    def default_preferences() -> EnergyPreferences:
        """Return default preferences."""
        return {
            "currency": "€",
            "home_consumption": [],
            "device_consumption": [],
            "production": [],
        }

    @callback
    def async_update(self, update: EnergyPreferencesUpdate) -> None:
        """Update the preferences."""
        if self.data is None:
            data = EnergyManager.default_preferences()
        else:
            data = self.data.copy()

        for key in (
            "currency",
            "home_consumption",
            "device_consumption",
            "production",
        ):
            if key in update:
                data[key] = update[key]  # type: ignore

        # TODO Validate stats exist

        self.data = data
        self._store.async_delay_save(lambda: cast(dict, self.data), 60)
