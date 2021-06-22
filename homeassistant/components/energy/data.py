"""Energy data."""
from __future__ import annotations

from typing import Optional, TypedDict, cast

import voluptuous as vol

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import singleton, storage

from .const import DOMAIN

STORAGE_VERSION = 1
STORAGE_KEY = DOMAIN


def ensure_home_valid_tariffs(value: dict) -> dict:
    """Ensure we only have a single tariff."""
    if ("stat_tariff" in value) and "tariff_kwh_low" in value:
        raise vol.Invalid("Either specify a tariff statistic or tariff calculation")

    return value


HOME_CONSUMPTION_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required("stat_consumption"): str,
            # Tariff. Either first, or the others.
            vol.Optional("stat_tariff"): vol.Any(None, str),
            vol.Inclusive("tariff_kwh_peak", "simple-tariff"): vol.Any(
                None, vol.Coerce(float)
            ),
            vol.Inclusive("tariff_kwh_off_peak", "simple-tariff"): vol.Any(
                None, vol.Coerce(float)
            ),
            vol.Inclusive("tariff_time_peak_start", "simple-tariff"): vol.Any(
                None, str
            ),
            vol.Inclusive("tariff_time_peak_stop", "simple-tariff"): vol.Any(None, str),
            # Costs
            vol.Required("cost_management_day"): vol.Coerce(float),
            vol.Required("cost_delivery_cost_day"): vol.Coerce(float),
            vol.Required("discount_energy_tax_day"): vol.Coerce(float),
        }
    ),
    ensure_home_valid_tariffs,
)
DEVICE_CONSUMPTION_SCHEMA = vol.Schema(
    {
        vol.Required("stat_consumption"): str,
    }
)
PRODUCTION_SCHEMA = vol.Schema(
    {
        vol.Required("type"): vol.In(("solar", "wind")),
        vol.Required("stat_generation"): str,
        vol.Optional("stat_return_to_grid"): vol.Any(str, None),
        vol.Optional("stat_predicted_generation"): vol.Any(str, None),
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

    # Points at a sensor that contains the cost
    stat_tariff: str | None

    # Basic tariff configuration, mutually exclusive with stat_tariff.
    # More complicated tariffs should get their own stat.
    tariff_kwh_peak: float | None
    tariff_kwh_off_peak: float | None
    tariff_time_peak_start: str | None
    tariff_time_peak_stop: str | None

    cost_management_day: float
    cost_delivery_cost_day: float
    discount_energy_tax_day: float


class EnergyDeviceConsumption(TypedDict):
    """Dictionary holding the source of individual device consumption."""

    # This is an ever increasing value
    stat_consumption: str


class EnergyProduction(TypedDict):
    """Dictionary holding the source of energy production."""

    type: str  # "solar" | "wind"

    stat_generation: str
    stat_return_to_grid: str | None
    stat_predicted_generation: str | None


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
            # TODO Can we default this based on timezones or GPS?
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
