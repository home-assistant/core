"""Mammotion binary sensor entities."""

from collections.abc import Callable
from dataclasses import dataclass

from pymammotion.data.model.device import MowingDevice

from homeassistant.components.binary_sensor import (
    ENTITY_ID_FORMAT,
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MammotionConfigEntry
from .coordinator import MammotionBaseUpdateCoordinator
from .entity import MammotionBaseEntity


@dataclass(frozen=True, kw_only=True)
class MammotionBinarySensorEntityDescription(
    BinarySensorEntityDescription,
):
    """Describes Mammotion binary sensor entity."""

    is_on_fn: Callable[[MowingDevice], bool | None]


BINARY_SENSORS: tuple[MammotionBinarySensorEntityDescription, ...] = (
    MammotionBinarySensorEntityDescription(
        key="charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        is_on_fn=lambda mower_data: mower_data.report_data.dev.charge_state in (1, 2),
    ),
)

"""
TODO:
read_and_set_sidelight(true, 1) is read
read_and_set_sidelight(bool, 0) is write
"""


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MammotionConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Mammotion sensor entity."""
    mammotion_devices = entry.runtime_data

    for mower in mammotion_devices:
        async_add_entities(
            MammotionBinarySensorEntity(mower.reporting_coordinator, entity_description)
            for entity_description in BINARY_SENSORS
        )


class MammotionBinarySensorEntity(MammotionBaseEntity, BinarySensorEntity):
    """Mammotion sensor entity."""

    entity_description: MammotionBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: MammotionBaseUpdateCoordinator,
        entity_description: MammotionBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor entity."""
        super().__init__(coordinator, entity_description.key)
        self.entity_id = ENTITY_ID_FORMAT.format(
            f"{coordinator.device_name}_{entity_description.key}"
        )
        self.entity_description = entity_description
        self._attr_translation_key = entity_description.translation_key

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.entity_description.is_on_fn(self.coordinator.data)
