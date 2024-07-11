"""Platform for Schlage binary_sensor integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import LockData, SchlageDataUpdateCoordinator
from .entity import SchlageEntity


@dataclass(frozen=True, kw_only=True)
class SchlageBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Entity description for a Schlage binary_sensor."""

    value_fn: Callable[[LockData], bool]


_DESCRIPTIONS: tuple[SchlageBinarySensorEntityDescription] = (
    SchlageBinarySensorEntityDescription(
        key="keypad_disabled",
        translation_key="keypad_disabled",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.lock.keypad_disabled(data.logs),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary_sensors based on a config entry."""
    coordinator: SchlageDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        SchlageBinarySensor(
            coordinator=coordinator,
            description=description,
            device_id=device_id,
        )
        for device_id in coordinator.data.locks
        for description in _DESCRIPTIONS
    )


class SchlageBinarySensor(SchlageEntity, BinarySensorEntity):
    """Schlage binary_sensor entity."""

    entity_description: SchlageBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: SchlageDataUpdateCoordinator,
        description: SchlageBinarySensorEntityDescription,
        device_id: str,
    ) -> None:
        """Initialize a SchlageBinarySensor."""
        super().__init__(coordinator, device_id)
        self.entity_description = description
        self._attr_unique_id = f"{device_id}_{self.entity_description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary_sensor is on."""
        return self.entity_description.value_fn(self._lock_data)
