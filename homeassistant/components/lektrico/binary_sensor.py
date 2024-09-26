"""Support for Lektrico binary sensors entities."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import ATTR_SERIAL_NUMBER, CONF_TYPE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LektricoConfigEntry, LektricoDeviceDataUpdateCoordinator
from .entity import LektricoEntity


@dataclass(frozen=True, kw_only=True)
class LektricoBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Lektrico binary sensor entity."""

    value_fn: Callable[[dict[str, Any]], bool]


BINARY_SENSORS: tuple[LektricoBinarySensorEntityDescription, ...] = (
    LektricoBinarySensorEntityDescription(
        key="errors",
        translation_key="errors",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda data: bool(data["has_active_errors"]),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LektricoConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Lektrico binary sensor entities based on a config entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        LektricoBinarySensor(
            description,
            coordinator,
            f"{entry.data[CONF_TYPE]}_{entry.data[ATTR_SERIAL_NUMBER]}",
        )
        for description in BINARY_SENSORS
    )


class LektricoBinarySensor(LektricoEntity, BinarySensorEntity):
    """Defines a Lektrico binary sensor entity."""

    entity_description: LektricoBinarySensorEntityDescription

    def __init__(
        self,
        description: LektricoBinarySensorEntityDescription,
        coordinator: LektricoDeviceDataUpdateCoordinator,
        device_name: str,
    ) -> None:
        """Initialize Lektrico binary sensor."""
        super().__init__(coordinator, device_name)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.serial_number}_{description.key}"

    @property
    def is_on(self) -> bool:
        """Return the state of the binary sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
