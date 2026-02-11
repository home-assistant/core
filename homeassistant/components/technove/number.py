"""Support for TechnoVE number entities."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from technove import MIN_CURRENT, TechnoVE

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import TechnoVEConfigEntry, TechnoVEDataUpdateCoordinator
from .entity import TechnoVEEntity
from .helpers import technove_exception_handler


@dataclass(frozen=True, kw_only=True)
class TechnoVENumberDescription(NumberEntityDescription):
    """Describes TechnoVE number entity."""

    native_max_value_fn: Callable[[TechnoVE], float]
    native_value_fn: Callable[[TechnoVE], float]
    set_value_fn: Callable[
        [TechnoVEDataUpdateCoordinator, float], Coroutine[Any, Any, None]
    ]


async def _set_max_current(
    coordinator: TechnoVEDataUpdateCoordinator, value: float
) -> None:
    if coordinator.data.info.in_sharing_mode:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="max_current_in_sharing_mode"
        )
    await coordinator.technove.set_max_current(value)


NUMBERS = [
    TechnoVENumberDescription(
        key="max_current",
        translation_key="max_current",
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.CURRENT,
        mode=NumberMode.BOX,
        native_step=1,
        native_min_value=MIN_CURRENT,
        native_max_value_fn=lambda station: station.info.max_station_current,
        native_value_fn=lambda station: station.info.max_current,
        set_value_fn=_set_max_current,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TechnoVEConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up TechnoVE number entity based on a config entry."""
    async_add_entities(
        TechnoVENumberEntity(entry.runtime_data, description) for description in NUMBERS
    )


class TechnoVENumberEntity(TechnoVEEntity, NumberEntity):
    """Defines a TechnoVE number entity."""

    entity_description: TechnoVENumberDescription

    def __init__(
        self,
        coordinator: TechnoVEDataUpdateCoordinator,
        description: TechnoVENumberDescription,
    ) -> None:
        """Initialize a TechnoVE switch entity."""
        self.entity_description = description
        super().__init__(coordinator, description.key)

    @property
    def native_max_value(self) -> float:
        """Return the max value of the TechnoVE number entity."""
        return self.entity_description.native_max_value_fn(self.coordinator.data)

    @property
    def native_value(self) -> float:
        """Return the native value of the TechnoVE number entity."""
        return self.entity_description.native_value_fn(self.coordinator.data)

    @technove_exception_handler
    async def async_set_native_value(self, value: float) -> None:
        """Set the value for the TechnoVE number entity."""
        await self.entity_description.set_value_fn(self.coordinator, value)
