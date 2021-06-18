"""Energy data."""
from __future__ import annotations

from typing import Optional, TypedDict, cast

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import singleton, storage

from .const import DOMAIN

STORAGE_VERSION = 1
STORAGE_KEY = DOMAIN


@singleton.singleton(DOMAIN)
async def async_get_manager(hass: HomeAssistant) -> EnergyManager:
    """Return an initialized data manager."""
    manager = EnergyManager(hass)
    await manager.async_initialize()
    return manager


class EnergyData(TypedDict):
    """Dictionary holding the energy data."""

    # This is a continues increasing value
    stat_house_energy_meter: str | None

    stat_solar_generatation: str | None
    stat_solar_return_to_grid: str | None
    stat_solar_predicted_generation: str | None

    stat_device_consumption: list[str]

    # The schedule of when low tariff applies
    schedule_tariff: None  # TODO data format

    cost_kwh_low_tariff: float | None
    cost_kwh_normal_tariff: float | None

    cost_grid_management_day: float  # Store as separate fields or not?
    cost_delivery_cost_day: float  # Store as separate fields or not?

    cost_discount_energy_tax_day: float  # Store as separate fields or not?


class EnergyDataUpdate(EnergyData, total=False):
    """all types optional."""


class EnergyManager:
    """Manage the instance energy prefs."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize energy manager."""
        self._hass = hass
        self._store = storage.Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self.data: EnergyData | None = None

    async def async_initialize(self) -> None:
        """Initialize the energy integration."""
        self.data = cast(Optional[EnergyData], await self._store.async_load())

    @staticmethod
    def default_preferences() -> EnergyData:
        """Return default preferences."""
        return {
            "stat_house_energy_meter": None,
            "stat_solar_generatation": None,
            "stat_solar_return_to_grid": None,
            "stat_solar_predicted_generation": None,
            "stat_device_consumption": [],
            "schedule_tariff": None,
            "cost_kwh_low_tariff": None,
            "cost_kwh_normal_tariff": None,
            "cost_grid_management_day": 0,
            "cost_delivery_cost_day": 0,
            "cost_discount_energy_tax_day": 0,
        }

    @callback
    def async_update(self, update: EnergyDataUpdate) -> None:
        """Update the preferences."""
        if self.data is None:
            data = EnergyManager.default_preferences()
        else:
            data = self.data.copy()

        for key in (
            "stat_house_energy_meter",
            "stat_solar_generatation",
            "stat_solar_return_to_grid",
            "stat_solar_predicted_generation",
            "stat_device_consumption",
            "schedule_tariff",
            "cost_kwh_low_tariff",
            "cost_kwh_normal_tariff",
            "cost_grid_management_day",
            "cost_delivery_cost_day",
            "cost_discount_energy_tax_day",
        ):
            if key in update:
                data[key] = update[key]  # type: ignore

        # TODO Validate stats exist

        self.data = data
        self._store.async_delay_save(lambda: cast(dict, self.data), 60)
