from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from pymammotion.data.model.device_config import DeviceLimits

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MammotionConfigEntry
from .coordinator import MammotionDataUpdateCoordinator
from .entity import MammotionBaseEntity


@dataclass(frozen=True, kw_only=True)
class MammotionNumberEntityDescription(NumberEntityDescription):
    """Describes Mammotion number entity."""

    set_fn: Callable[[MammotionDataUpdateCoordinator, float], Awaitable[None]]


NUMBER_ENTITIES: tuple[MammotionNumberEntityDescription, ...] = (
    MammotionNumberEntityDescription(
        key="start_progress",
        min_value=0,
        max_value=100,
        step=1,
        mode=NumberMode.SLIDER,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.CONFIG,
        set_fn=lambda coordinator, value: value,
    ),
)


NUMBER_WORKING_ENTITIES: tuple[MammotionNumberEntityDescription, ...] = (
    MammotionNumberEntityDescription(
        key="blade_height",
        step=5.0,
        min_value=30.0,  # ToDo: To be dynamiclly set based on model (h\non H)
        max_value=70.0,  # ToDo: To be dynamiclly set based on model (h\non H)
        entity_category=EntityCategory.CONFIG,
        set_fn=lambda coordinator, value: coordinator.async_blade_height(value),
    ),
    MammotionNumberEntityDescription(
        key="working_speed",
        entity_category=EntityCategory.CONFIG,
        step=0.1,
        min_value=0.2,
        max_value=0.6,
        set_fn=lambda coordinator, value: value,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MammotionConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Mammotion number entities."""
    coordinator = entry.runtime_data
    limits = coordinator.devices.mower(coordinator.device_name).limits

    entities: list[MammotionNumberEntity] = []

    for entity_description in NUMBER_WORKING_ENTITIES:
        entity = MammotionWorkingNumberEntity(coordinator, entity_description, limits)
        entities.append(entity)

    for entity_description in NUMBER_ENTITIES:
        entity = MammotionNumberEntity(coordinator, entity_description)
        entities.append(entity)

    async_add_entities(entities)


class MammotionNumberEntity(MammotionBaseEntity, NumberEntity):
    entity_description: MammotionNumberEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MammotionDataUpdateCoordinator,
        entity_description: MammotionNumberEntityDescription,
    ) -> None:
        super().__init__(coordinator, entity_description.key)
        self.entity_description = entity_description
        self._attr_translation_key = entity_description.key
        self._attr_native_min_value = entity_description.min_value
        self._attr_native_max_value = entity_description.max_value
        self._attr_native_step = entity_description.step
        self._attr_native_value = self._attr_native_min_value  # Default value

    async def async_set_native_value(self, value: float) -> None:
        self._attr_native_value = value
        await self.entity_description.set_fn(self.coordinator, value)
        self.async_write_ha_state()


class MammotionWorkingNumberEntity(MammotionNumberEntity):
    """Mammotion working number entity."""

    def __init__(
        self,
        coordinator: MammotionDataUpdateCoordinator,
        entity_description: MammotionNumberEntityDescription,
        limits: DeviceLimits,
    ) -> None:
        super().__init__(coordinator, entity_description)

        min_attr = f"{entity_description.key}_min"
        max_attr = f"{entity_description.key}_max"

        if hasattr(limits, min_attr) and hasattr(limits, max_attr):
            self._attr_native_min_value = getattr(limits, min_attr)
            self._attr_native_max_value = getattr(limits, max_attr)
        else:
            # Fallback to the values from entity_description
            self._attr_native_min_value = entity_description.min_value
            self._attr_native_max_value = entity_description.max_value

    @property
    def native_min_value(self) -> float:
        """Return the minimum value."""
        return self._attr_native_min_value

    @property
    def native_max_value(self) -> float:
        """Return the maximum value."""
        return self._attr_native_max_value
