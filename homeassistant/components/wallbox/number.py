"""Home Assistant component for accessing the Wallbox Portal API.

The number component allows control of charging current.
"""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, cast

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    BIDIRECTIONAL_MODEL_PREFIXES,
    CHARGER_DATA_KEY,
    CHARGER_ENERGY_PRICE_KEY,
    CHARGER_MAX_AVAILABLE_POWER_KEY,
    CHARGER_MAX_CHARGING_CURRENT_KEY,
    CHARGER_PART_NUMBER_KEY,
    CHARGER_SERIAL_NUMBER_KEY,
    DOMAIN,
)
from .coordinator import InvalidAuth, WallboxCoordinator
from .entity import WallboxEntity


def max_charging_current_value(coordinator: WallboxCoordinator) -> float:
    """Return the maximum available value for charging current."""
    return cast(float, coordinator.data[CHARGER_MAX_AVAILABLE_POWER_KEY])


def min_charging_current_value(coordinator: WallboxCoordinator) -> float:
    """Return the minimum available value for charging current."""
    return cast(
        float,
        (
            coordinator.data[CHARGER_MAX_AVAILABLE_POWER_KEY] * -1
            if coordinator.data[CHARGER_DATA_KEY][CHARGER_PART_NUMBER_KEY][0:2]
            in BIDIRECTIONAL_MODEL_PREFIXES
            else 0
        ),
    )


async def async_set_charging_current_value(
    coordinator: WallboxCoordinator, value: float
) -> None:
    """Set the value for charging current."""
    await coordinator.async_set_charging_current(value)


def max_energy_price_value(coordinator: WallboxCoordinator) -> float:
    """Return the maximum available value for energy price."""
    return 5


def min_energy_price_value(coordinator: WallboxCoordinator) -> float:
    """Return the maximum available value for energy price."""
    return -5


async def async_set_energy_price_value(
    coordinator: WallboxCoordinator, value: float
) -> None:
    """Set the value for energy price."""
    await coordinator.async_set_energy_cost(value)


@dataclass
class WallboxNumberEntityDescriptionMixin:
    """Load entities from different handlers."""

    max_value_fn: Callable[[WallboxCoordinator], float]
    min_value_fn: Callable[[WallboxCoordinator], float]
    set_value_fn: Callable[[WallboxCoordinator, float], Coroutine[Any, Any, Any]]


@dataclass
class WallboxNumberEntityDescription(
    NumberEntityDescription, WallboxNumberEntityDescriptionMixin
):
    """Describes Wallbox number entity."""


NUMBER_TYPES: dict[str, WallboxNumberEntityDescription] = {
    CHARGER_MAX_CHARGING_CURRENT_KEY: WallboxNumberEntityDescription(
        key=CHARGER_MAX_CHARGING_CURRENT_KEY,
        translation_key="maximum_charging_current",
        max_value_fn=max_charging_current_value,
        min_value_fn=min_charging_current_value,
        set_value_fn=async_set_charging_current_value,
        native_step=1,
    ),
    CHARGER_ENERGY_PRICE_KEY: WallboxNumberEntityDescription(
        key=CHARGER_ENERGY_PRICE_KEY,
        translation_key="energy_price",
        max_value_fn=max_energy_price_value,
        min_value_fn=min_energy_price_value,
        set_value_fn=async_set_energy_price_value,
        native_step=0.01,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create wallbox number entities in HASS."""
    coordinator: WallboxCoordinator = hass.data[DOMAIN][entry.entry_id]
    # Check if the user has sufficient rights to change values, if so, add number component:
    try:
        await coordinator.async_set_charging_current(
            coordinator.data[CHARGER_MAX_CHARGING_CURRENT_KEY]
        )
    except InvalidAuth:
        return
    except ConnectionError as exc:
        raise PlatformNotReady from exc

    async_add_entities(
        [
            WallboxNumber(coordinator, entry, description)
            for ent in coordinator.data
            if (description := NUMBER_TYPES.get(ent))
        ]
    )


class WallboxNumber(WallboxEntity, NumberEntity):
    """Representation of the Wallbox portal."""

    entity_description: WallboxNumberEntityDescription

    def __init__(
        self,
        coordinator: WallboxCoordinator,
        entry: ConfigEntry,
        description: WallboxNumberEntityDescription,
    ) -> None:
        """Initialize a Wallbox number entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._coordinator = coordinator
        self._attr_unique_id = f"{description.key}-{coordinator.data[CHARGER_DATA_KEY][CHARGER_SERIAL_NUMBER_KEY]}"

    @property
    def native_max_value(self) -> float:
        """Return the maximum available value."""
        return self.entity_description.max_value_fn(self.coordinator)

    @property
    def native_min_value(self) -> float:
        """Return the minimum available value."""
        return self.entity_description.min_value_fn(self.coordinator)

    @property
    def native_value(self) -> float | None:
        """Return the value of the entity."""
        return cast(float | None, self._coordinator.data[self.entity_description.key])

    async def async_set_native_value(self, value: float) -> None:
        """Set the value of the entity."""
        await self.entity_description.set_value_fn(self.coordinator, value)
