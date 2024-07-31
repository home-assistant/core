"""Number platform for V2C settings."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from pytrydan import Trydan, TrydanData

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.const import EntityCategory, UnitOfElectricCurrent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import V2CConfigEntry
from .coordinator import V2CUpdateCoordinator
from .entity import V2CBaseEntity

MIN_INTENSITY = 6
MAX_INTENSITY = 32


@dataclass(frozen=True, kw_only=True)
class V2CSettingsNumberEntityDescription(NumberEntityDescription):
    """Describes V2C EVSE number entity."""

    value_fn: Callable[[TrydanData], int]
    update_fn: Callable[[Trydan, int], Coroutine[Any, Any, None]]


TRYDAN_NUMBER_SETTINGS = (
    V2CSettingsNumberEntityDescription(
        key="intensity",
        translation_key="intensity",
        device_class=NumberDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        native_min_value=MIN_INTENSITY,
        native_max_value=MAX_INTENSITY,
        value_fn=lambda evse_data: evse_data.intensity,
        update_fn=lambda evse, value: evse.intensity(value),
    ),
    V2CSettingsNumberEntityDescription(
        key="min_intensity",
        translation_key="min_intensity",
        device_class=NumberDeviceClass.CURRENT,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        native_min_value=MIN_INTENSITY,
        native_max_value=MAX_INTENSITY,
        value_fn=lambda evse_data: evse_data.min_intensity,
        update_fn=lambda evse, value: evse.min_intensity(value),
    ),
    V2CSettingsNumberEntityDescription(
        key="max_intensity",
        translation_key="max_intensity",
        device_class=NumberDeviceClass.CURRENT,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        native_min_value=MIN_INTENSITY,
        native_max_value=MAX_INTENSITY,
        value_fn=lambda evse_data: evse_data.max_intensity,
        update_fn=lambda evse, value: evse.max_intensity(value),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: V2CConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up V2C Trydan number platform."""
    coordinator = config_entry.runtime_data

    async_add_entities(
        V2CSettingsNumberEntity(coordinator, description, config_entry.entry_id)
        for description in TRYDAN_NUMBER_SETTINGS
    )


class V2CSettingsNumberEntity(V2CBaseEntity, NumberEntity):
    """Representation of V2C EVSE settings number entity."""

    entity_description: V2CSettingsNumberEntityDescription

    def __init__(
        self,
        coordinator: V2CUpdateCoordinator,
        description: V2CSettingsNumberEntityDescription,
        entry_id: str,
    ) -> None:
        """Initialize the V2C number entity."""
        super().__init__(coordinator, description)
        self._attr_unique_id = f"{entry_id}_{description.key}"

    @property
    def native_value(self) -> float:
        """Return the state of the setting entity."""
        return self.entity_description.value_fn(self.data)

    async def async_set_native_value(self, value: float) -> None:
        """Update the setting."""
        await self.entity_description.update_fn(self.coordinator.evse, int(value))
        await self.coordinator.async_request_refresh()
