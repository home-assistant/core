"""Energy data."""
from __future__ import annotations

from collections import Counter
from typing import Awaitable, Callable, Literal, Optional, TypedDict, Union, cast

import voluptuous as vol

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, singleton, storage

from .const import DOMAIN

STORAGE_VERSION = 1
STORAGE_KEY = DOMAIN


@singleton.singleton(DOMAIN)
async def async_get_manager(hass: HomeAssistant) -> EnergyManager:
    """Return an initialized data manager."""
    manager = EnergyManager(hass)
    await manager.async_initialize()
    return manager


class FlowFromGridSourceType(TypedDict):
    """Dictionary describing the 'from' stat for the grid source."""

    # statistic_id of a an energy meter (kWh)
    stat_energy_from: str

    # statistic_id of costs ($) incurred from the energy meter
    # If set to None and entity_energy_from and entity_energy_price are configured,
    # an EnergyCostSensor will be automatically created
    stat_cost: str | None

    # Used to generate costs if stat_cost is set to None
    entity_energy_from: str | None  # entity_id of an energy meter (kWh), entity_id of the energy meter for stat_energy_from
    entity_energy_price: str | None  # entity_id of an entity providing price ($/kWh)
    number_energy_price: float | None  # Price for energy ($/kWh)


class FlowToGridSourceType(TypedDict):
    """Dictionary describing the 'to' stat for the grid source."""

    # kWh meter
    stat_energy_to: str


class GridSourceType(TypedDict):
    """Dictionary holding the source of grid energy consumption."""

    type: Literal["grid"]

    flow_from: list[FlowFromGridSourceType]
    flow_to: list[FlowToGridSourceType]

    cost_adjustment_day: float


class SolarSourceType(TypedDict):
    """Dictionary holding the source of energy production."""

    type: Literal["solar"]

    stat_energy_from: str
    stat_predicted_energy_from: str | None


SourceType = Union[GridSourceType, SolarSourceType]


class DeviceConsumption(TypedDict):
    """Dictionary holding the source of individual device consumption."""

    # This is an ever increasing value
    stat_consumption: str


class EnergyPreferences(TypedDict):
    """Dictionary holding the energy data."""

    currency: str
    energy_sources: list[SourceType]
    device_consumption: list[DeviceConsumption]


class EnergyPreferencesUpdate(EnergyPreferences, total=False):
    """all types optional."""


def _flow_from_ensure_single_price(
    val: FlowFromGridSourceType,
) -> FlowFromGridSourceType:
    """Ensure we use a single price source."""
    if (
        val["entity_energy_price"] is not None
        and val["number_energy_price"] is not None
    ):
        raise vol.Invalid("Define either an entity or a fixed number for the price")

    return val


FLOW_FROM_GRID_SOURCE_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required("stat_energy_from"): str,
            vol.Required("stat_cost"): vol.Any(None, str),
            vol.Required("entity_energy_from"): vol.Any(None, str),
            vol.Required("entity_energy_price"): vol.Any(None, str),
            vol.Required("number_energy_price"): vol.Any(None, vol.Coerce(float)),
        }
    ),
    _flow_from_ensure_single_price,
)


FLOW_TO_GRID_SOURCE_SCHEMA = vol.Schema(
    {
        vol.Required("stat_energy_to"): str,
    }
)


def _flow_from_ensure_energy_from_stat_unique(
    val: list[FlowFromGridSourceType],
) -> list[FlowFromGridSourceType]:
    """Ensure that the user doesn't add duplicate stats to grid sources."""
    counts = Counter(flow_from["stat_energy_from"] for flow_from in val)

    for stat, count in counts.items():
        if count > 1:
            raise vol.Invalid(f"Cannot specify {stat} more than once")

    return val


GRID_SOURCE_SCHEMA = vol.Schema(
    {
        vol.Required("type"): "grid",
        vol.Required("flow_from"): vol.All(
            [FLOW_FROM_GRID_SOURCE_SCHEMA],
            vol.Length(min=1),
            _flow_from_ensure_energy_from_stat_unique,
        ),
        vol.Required("flow_to"): [FLOW_TO_GRID_SOURCE_SCHEMA],
        vol.Required("cost_adjustment_day"): vol.Coerce(float),
    }
)
SOLAR_SOURCE_SCHEMA = vol.Schema(
    {
        vol.Required("type"): "solar",
        vol.Required("stat_energy_from"): str,
        vol.Required("stat_predicted_energy_from"): vol.Any(str, None),
    }
)


def check_type_limits(value: list[SourceType]) -> list[SourceType]:
    """Validate that we don't have too many of certain types."""
    types = Counter([val["type"] for val in value])

    for source_type, source_count in types.items():
        if source_count > 1:
            raise vol.Invalid(f"You cannot have more than 1 {source_type} source")

    return value


ENERGY_SOURCE_SCHEMA = vol.All(
    vol.Schema(
        [
            cv.key_value_schemas(
                "type",
                {
                    "grid": GRID_SOURCE_SCHEMA,
                    "solar": SOLAR_SOURCE_SCHEMA,
                },
            )
        ]
    ),
    check_type_limits,
)

DEVICE_CONSUMPTION_SCHEMA = vol.Schema(
    {
        vol.Required("stat_consumption"): str,
    }
)


class EnergyManager:
    """Manage the instance energy prefs."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize energy manager."""
        self._hass = hass
        self._store = storage.Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self.data: EnergyPreferences | None = None
        self._update_listeners: list[Callable[[], Awaitable]] = []

    async def async_initialize(self) -> None:
        """Initialize the energy integration."""
        self.data = cast(Optional[EnergyPreferences], await self._store.async_load())

    @staticmethod
    def default_preferences() -> EnergyPreferences:
        """Return default preferences."""
        return {
            "currency": "€",
            "energy_sources": [],
            "device_consumption": [],
        }

    async def async_update(self, update: EnergyPreferencesUpdate) -> None:
        """Update the preferences."""
        if self.data is None:
            data = EnergyManager.default_preferences()
        else:
            data = self.data.copy()

        for key in (
            "currency",
            "energy_sources",
            "device_consumption",
        ):
            if key in update:
                data[key] = update[key]  # type: ignore

        # TODO Validate stats exist

        self.data = data
        self._store.async_delay_save(lambda: cast(dict, self.data), 60)

        for listener in self._update_listeners:
            await listener()

    @callback
    def async_listen_updates(self, update_listener: Callable[[], Awaitable]) -> None:
        """Listen for data updates."""
        self._update_listeners.append(update_listener)
