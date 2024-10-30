from dataclasses import dataclass
from typing import Callable

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import (
    AREA_SQUARE_METERS,
    DEGREE,
    PERCENTAGE,
    UnitOfLength,
    UnitOfSpeed,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from pymammotion.data.model.device_config import DeviceLimits
from pymammotion.utility.device_type import DeviceType

from . import MammotionConfigEntry
from .coordinator import MammotionDataUpdateCoordinator
from .entity import MammotionBaseEntity


@dataclass(frozen=True, kw_only=True)
class MammotionConfigNumberEntityDescription(NumberEntityDescription):
    """Describes Mammotion number entity."""

    set_fn: Callable[[MammotionDataUpdateCoordinator, int], None]


NUMBER_ENTITIES: tuple[MammotionConfigNumberEntityDescription, ...] = (
    MammotionConfigNumberEntityDescription(
        key="start_progress",
        min_value=0,
        max_value=100,
        step=1,
        mode=NumberMode.SLIDER,
        native_unit_of_measurement=PERCENTAGE,
        set_fn=lambda coordinator, value: setattr(
            coordinator.operation_settings, "start_progress", value
        ),
    ),
    MammotionConfigNumberEntityDescription(
        key="cutting_angle",
        step=1,
        native_unit_of_measurement=DEGREE,
        min_value=-180,
        max_value=180,
        set_fn=lambda coordinator, value: setattr(
            coordinator.operation_settings, "toward", value
        ),
    ),
    MammotionConfigNumberEntityDescription(
        key="toward_included_angle",
        step=1,
        native_unit_of_measurement=DEGREE,
        min_value=-180,
        max_value=180,
        set_fn=lambda coordinator, value: setattr(
            coordinator.operation_settings, "toward_included_angle", value
        ),
    ),
)

YUKA_NUMBER_ENTITIES: tuple[MammotionConfigNumberEntityDescription, ...] = (
    MammotionConfigNumberEntityDescription(
        key="dumping_interval",
        min_value=5,
        max_value=100,
        step=1,
        mode=NumberMode.SLIDER,
        native_unit_of_measurement=AREA_SQUARE_METERS,
        set_fn=lambda coordinator, value: setattr(
            coordinator.operation_settings, "collect_grass_frequency", value
        ),
    ),
)

LUBA_WORKING_ENTITIES: tuple[MammotionConfigNumberEntityDescription, ...] = (
    MammotionConfigNumberEntityDescription(
        key="blade_height",
        step=5,
        min_value=25,  # ToDo: To be dynamiclly set based on model (h\non H)
        max_value=70,  # ToDo: To be dynamiclly set based on model (h\non H)
        set_fn=lambda coordinator, value: setattr(
            coordinator.operation_settings, "blade_height", value
        ),
    ),
)


NUMBER_WORKING_ENTITIES: tuple[MammotionConfigNumberEntityDescription, ...] = (
    MammotionConfigNumberEntityDescription(
        key="working_speed",
        device_class=NumberDeviceClass.SPEED,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        step=0.1,
        min_value=0.2,
        max_value=0.6,
        set_fn=lambda coordinator, value: setattr(
            coordinator.operation_settings, "speed", value
        ),
    ),
    MammotionConfigNumberEntityDescription(
        key="path_spacing",
        step=1,
        device_class=NumberDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.CENTIMETERS,
        min_value=20,
        max_value=35,
        set_fn=lambda coordinator, value: setattr(
            coordinator.operation_settings, "channel_width", value
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MammotionConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Mammotion number entities."""
    coordinator = entry.runtime_data
    limits = coordinator.manager.mower(coordinator.device_name).limits

    entities: list[MammotionConfigNumberEntity] = []

    for entity_description in NUMBER_WORKING_ENTITIES:
        entity = MammotionWorkingNumberEntity(coordinator, entity_description, limits)
        entities.append(entity)

    for entity_description in NUMBER_ENTITIES:
        entity = MammotionConfigNumberEntity(coordinator, entity_description)
        entities.append(entity)

    if DeviceType.is_yuka(coordinator.device_name):
        for entity_description in YUKA_NUMBER_ENTITIES:
            entity = MammotionConfigNumberEntity(coordinator, entity_description)
            entities.append(entity)
    else:
        for entity_description in LUBA_WORKING_ENTITIES:
            entity = MammotionWorkingNumberEntity(
                coordinator, entity_description, limits
            )
            entities.append(entity)

    async_add_entities(entities)


class MammotionConfigNumberEntity(MammotionBaseEntity, NumberEntity, RestoreEntity):
    entity_description: MammotionConfigNumberEntityDescription
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: MammotionDataUpdateCoordinator,
        entity_description: MammotionConfigNumberEntityDescription,
    ) -> None:
        super().__init__(coordinator, entity_description.key)
        self.entity_description = entity_description
        self._attr_translation_key = entity_description.key
        self._attr_native_min_value = entity_description.min_value
        self._attr_native_max_value = entity_description.max_value
        self._attr_native_step = entity_description.step
        self._attr_native_value = self._attr_native_min_value  # Default value
        if self.entity_description.native_unit_of_measurement == DEGREE:
            self._attr_native_value = 0
        if self.entity_description.key == "toward_included_angle":
            self._attr_native_value = 90

    async def async_set_native_value(self, value: float | int) -> None:
        self._attr_native_value = value
        self.entity_description.set_fn(self.coordinator, value)
        self.async_write_ha_state()


class MammotionWorkingNumberEntity(MammotionConfigNumberEntity):
    """Mammotion working number entity."""

    def __init__(
        self,
        coordinator: MammotionDataUpdateCoordinator,
        entity_description: MammotionConfigNumberEntityDescription,
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

    async def async_set_native_value(self, value: float | int) -> None:
        self._attr_native_value = value
        self.entity_description.set_fn(self.coordinator, value)
        self.async_write_ha_state()
