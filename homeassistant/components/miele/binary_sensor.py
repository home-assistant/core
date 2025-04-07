"""Binary sensor platform for Miele integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any, Final

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import MieleAppliance
from .coordinator import MieleConfigEntry, MieleDataUpdateCoordinator
from .entity import MieleEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class MieleBinarySensorDescription(BinarySensorEntityDescription):
    """Class describing Miele binary sensor entities."""

    data_tag: str
    convert: Callable[[Any], Any] | None = None


@dataclass
class MieleBinarySensorDefinition:
    """Class for defining binary sensor entities."""

    types: tuple[MieleAppliance, ...]
    description: MieleBinarySensorDescription


BINARY_SENSOR_TYPES: Final[tuple[MieleBinarySensorDefinition, ...]] = (
    MieleBinarySensorDefinition(
        types=(
            MieleAppliance.DISH_WARMER,
            MieleAppliance.DISHWASHER,
            MieleAppliance.FREEZER,
            MieleAppliance.FRIDGE_FREEZER,
            MieleAppliance.FRIDGE,
            MieleAppliance.MICROWAVE,
            MieleAppliance.OVEN_MICROWAVE,
            MieleAppliance.OVEN,
            MieleAppliance.STEAM_OVEN_COMBI,
            MieleAppliance.STEAM_OVEN_MICRO,
            MieleAppliance.STEAM_OVEN_MK2,
            MieleAppliance.STEAM_OVEN,
            MieleAppliance.TUMBLE_DRYER_SEMI_PROFESSIONAL,
            MieleAppliance.TUMBLE_DRYER,
            MieleAppliance.WASHER_DRYER,
            MieleAppliance.WASHING_MACHINE_SEMI_PROFESSIONAL,
            MieleAppliance.WASHING_MACHINE,
            MieleAppliance.WINE_CABINET_FREEZER,
            MieleAppliance.WINE_CABINET,
            MieleAppliance.WINE_CONDITIONING_UNIT,
            MieleAppliance.WINE_STORAGE_CONDITIONING_UNIT,
        ),
        description=MieleBinarySensorDescription(
            key="state_signal_door",
            data_tag="state_signal_door",
            device_class=BinarySensorDeviceClass.DOOR,
            translation_key="door",
        ),
    ),
    MieleBinarySensorDefinition(
        types=(
            MieleAppliance.WASHING_MACHINE,
            MieleAppliance.WASHING_MACHINE_SEMI_PROFESSIONAL,
            MieleAppliance.TUMBLE_DRYER,
            MieleAppliance.TUMBLE_DRYER_SEMI_PROFESSIONAL,
            MieleAppliance.DISHWASHER,
            MieleAppliance.OVEN,
            MieleAppliance.OVEN_MICROWAVE,
            MieleAppliance.STEAM_OVEN,
            MieleAppliance.MICROWAVE,
            MieleAppliance.COFFEE_SYSTEM,
            MieleAppliance.HOOD,
            MieleAppliance.FRIDGE,
            MieleAppliance.FREEZER,
            MieleAppliance.FRIDGE_FREEZER,
            MieleAppliance.ROBOT_VACUUM_CLEANER,
            MieleAppliance.WASHER_DRYER,
            MieleAppliance.DISH_WARMER,
            MieleAppliance.STEAM_OVEN_COMBI,
            MieleAppliance.WINE_CABINET,
            MieleAppliance.WINE_CONDITIONING_UNIT,
            MieleAppliance.WINE_STORAGE_CONDITIONING_UNIT,
            MieleAppliance.STEAM_OVEN_MICRO,
            MieleAppliance.DIALOG_OVEN,
            MieleAppliance.WINE_CABINET_FREEZER,
            MieleAppliance.STEAM_OVEN_MK2,
        ),
        description=MieleBinarySensorDescription(
            key="state_signal_info",
            data_tag="state_signal_info",
            device_class=BinarySensorDeviceClass.PROBLEM,
            translation_key="info",
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
    ),
    MieleBinarySensorDefinition(
        types=(
            MieleAppliance.COFFEE_SYSTEM,
            MieleAppliance.DIALOG_OVEN,
            MieleAppliance.DISH_WARMER,
            MieleAppliance.DISHWASHER,
            MieleAppliance.FREEZER,
            MieleAppliance.FRIDGE_FREEZER,
            MieleAppliance.FRIDGE,
            MieleAppliance.HOB_HIGHLIGHT,
            MieleAppliance.HOB_INDUCT_EXTR,
            MieleAppliance.HOB_INDUCTION,
            MieleAppliance.HOOD,
            MieleAppliance.MICROWAVE,
            MieleAppliance.OVEN_MICROWAVE,
            MieleAppliance.OVEN,
            MieleAppliance.ROBOT_VACUUM_CLEANER,
            MieleAppliance.STEAM_OVEN_COMBI,
            MieleAppliance.STEAM_OVEN_MICRO,
            MieleAppliance.STEAM_OVEN_MK2,
            MieleAppliance.STEAM_OVEN,
            MieleAppliance.TUMBLE_DRYER_SEMI_PROFESSIONAL,
            MieleAppliance.TUMBLE_DRYER,
            MieleAppliance.WASHER_DRYER,
            MieleAppliance.WASHING_MACHINE_SEMI_PROFESSIONAL,
            MieleAppliance.WASHING_MACHINE,
            MieleAppliance.WINE_CABINET_FREEZER,
            MieleAppliance.WINE_CABINET,
            MieleAppliance.WINE_CONDITIONING_UNIT,
            MieleAppliance.WINE_STORAGE_CONDITIONING_UNIT,
        ),
        description=MieleBinarySensorDescription(
            key="state_signal_failure",
            data_tag="state_signal_failure",
            device_class=BinarySensorDeviceClass.PROBLEM,
            translation_key="failure",
            icon="mdi:alert",
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
    ),
    MieleBinarySensorDefinition(
        types=(
            MieleAppliance.WASHING_MACHINE,
            MieleAppliance.WASHING_MACHINE_SEMI_PROFESSIONAL,
            MieleAppliance.TUMBLE_DRYER,
            MieleAppliance.TUMBLE_DRYER_SEMI_PROFESSIONAL,
            MieleAppliance.DISHWASHER,
            MieleAppliance.DISH_WARMER,
            MieleAppliance.OVEN,
            MieleAppliance.OVEN_MICROWAVE,
            MieleAppliance.STEAM_OVEN,
            MieleAppliance.MICROWAVE,
            MieleAppliance.COFFEE_SYSTEM,
            MieleAppliance.HOOD,
            MieleAppliance.FRIDGE,
            MieleAppliance.FREEZER,
            MieleAppliance.FRIDGE_FREEZER,
            MieleAppliance.ROBOT_VACUUM_CLEANER,
            MieleAppliance.WASHER_DRYER,
            MieleAppliance.STEAM_OVEN_COMBI,
            MieleAppliance.WINE_CABINET,
            MieleAppliance.WINE_CONDITIONING_UNIT,
            MieleAppliance.WINE_STORAGE_CONDITIONING_UNIT,
            MieleAppliance.STEAM_OVEN_MICRO,
            MieleAppliance.DIALOG_OVEN,
            MieleAppliance.WINE_CABINET_FREEZER,
            MieleAppliance.STEAM_OVEN_MK2,
            MieleAppliance.HOB_INDUCT_EXTR,
        ),
        description=MieleBinarySensorDescription(
            key="state_full_remote_control",
            data_tag="state_full_remote_control",
            translation_key="remote_control",
            icon="mdi:remote",
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
    ),
    MieleBinarySensorDefinition(
        types=(
            MieleAppliance.WASHING_MACHINE,
            MieleAppliance.WASHING_MACHINE_SEMI_PROFESSIONAL,
            MieleAppliance.TUMBLE_DRYER,
            MieleAppliance.TUMBLE_DRYER_SEMI_PROFESSIONAL,
            MieleAppliance.DISHWASHER,
            MieleAppliance.OVEN,
            MieleAppliance.OVEN_MICROWAVE,
            MieleAppliance.STEAM_OVEN,
            MieleAppliance.MICROWAVE,
            MieleAppliance.COFFEE_SYSTEM,
            MieleAppliance.HOOD,
            MieleAppliance.FRIDGE,
            MieleAppliance.FREEZER,
            MieleAppliance.FRIDGE_FREEZER,
            MieleAppliance.ROBOT_VACUUM_CLEANER,
            MieleAppliance.WASHER_DRYER,
            MieleAppliance.STEAM_OVEN_COMBI,
            MieleAppliance.WINE_CABINET,
            MieleAppliance.WINE_CONDITIONING_UNIT,
            MieleAppliance.WINE_STORAGE_CONDITIONING_UNIT,
            MieleAppliance.STEAM_OVEN_MICRO,
            MieleAppliance.DIALOG_OVEN,
            MieleAppliance.WINE_CABINET_FREEZER,
            MieleAppliance.STEAM_OVEN_MK2,
            MieleAppliance.HOB_INDUCT_EXTR,
        ),
        description=MieleBinarySensorDescription(
            key="state_smart_grid",
            data_tag="state_smart_grid",
            translation_key="smart_grid",
            icon="mdi:view-grid-plus-outline",
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
        ),
    ),
    MieleBinarySensorDefinition(
        types=(
            MieleAppliance.WASHING_MACHINE,
            MieleAppliance.WASHING_MACHINE_SEMI_PROFESSIONAL,
            MieleAppliance.TUMBLE_DRYER,
            MieleAppliance.TUMBLE_DRYER_SEMI_PROFESSIONAL,
            MieleAppliance.DISHWASHER,
            MieleAppliance.DISH_WARMER,
            MieleAppliance.OVEN,
            MieleAppliance.OVEN_MICROWAVE,
            MieleAppliance.STEAM_OVEN,
            MieleAppliance.MICROWAVE,
            MieleAppliance.COFFEE_SYSTEM,
            MieleAppliance.HOOD,
            MieleAppliance.FRIDGE,
            MieleAppliance.FREEZER,
            MieleAppliance.FRIDGE_FREEZER,
            MieleAppliance.ROBOT_VACUUM_CLEANER,
            MieleAppliance.WASHER_DRYER,
            MieleAppliance.STEAM_OVEN_COMBI,
            MieleAppliance.WINE_CABINET,
            MieleAppliance.WINE_CONDITIONING_UNIT,
            MieleAppliance.WINE_STORAGE_CONDITIONING_UNIT,
            MieleAppliance.STEAM_OVEN_MICRO,
            MieleAppliance.DIALOG_OVEN,
            MieleAppliance.WINE_CABINET_FREEZER,
            MieleAppliance.STEAM_OVEN_MK2,
            MieleAppliance.HOB_INDUCT_EXTR,
        ),
        description=MieleBinarySensorDescription(
            key="state_mobile_start",
            data_tag="state_mobile_start",
            translation_key="mobile_start",
            icon="mdi:cellphone-wireless",
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MieleConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator = config_entry.runtime_data

    entities = [
        MieleBinarySensor(coordinator, device_id, definition.description)
        for device_id, device in coordinator.data.devices.items()
        for definition in BINARY_SENSOR_TYPES
        if device.device_type in definition.types
    ]

    async_add_entities(entities)


class MieleBinarySensor(MieleEntity, BinarySensorEntity):
    """Representation of a Binary Sensor."""

    entity_description: MieleBinarySensorDescription

    def __init__(
        self,
        coordinator: MieleDataUpdateCoordinator,
        device_id: str,
        description: MieleBinarySensorDescription,
    ) -> None:
        """Initialize the sensor."""
        self.device = coordinator.data.devices[device_id]
        super().__init__(coordinator, device_id, description)

    @property
    def is_on(self) -> bool | None:
        """Return the state of the sensor."""
        return getattr(
            self.coordinator.data.devices[self._device_id],
            self.entity_description.data_tag,
            None,
        )
