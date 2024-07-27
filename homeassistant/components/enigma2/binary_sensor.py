"""Binary sensors for the Enigma2 integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from openwebif.api import OpenWebIfDevice

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import Enigma2ConfigEntry
from .coordinator import Enigma2UpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class Enigma2BinarySensorDescription(BinarySensorEntityDescription):
    """Describes Enigma2 binary sensors."""

    value_fn: Callable[[OpenWebIfDevice], bool]


BINARY_SENSOR_TYPES: list[Enigma2BinarySensorDescription] = [
    Enigma2BinarySensorDescription(
        value_fn=lambda device: bool(device.status.is_recording),
        key="is_recording",
        translation_key="is_recording",
    )
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Enigma2ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Webmin sensors based on a config entry."""
    async_add_entities(
        [
            Enigma2BinarySensor(entry.runtime_data, description)
            for description in BINARY_SENSOR_TYPES
        ]
    )


class Enigma2BinarySensor(
    CoordinatorEntity[Enigma2UpdateCoordinator], BinarySensorEntity
):
    """Represents a Enigma2 binary sensor."""

    entity_description: Enigma2BinarySensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: Enigma2UpdateCoordinator,
        description: Enigma2BinarySensorDescription,
    ) -> None:
        """Initialize a Enigma2 binary sensor."""

        super().__init__(coordinator)
        self.entity_description = description
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{(
            coordinator.device.mac_address
            or cast(ConfigEntry, coordinator.config_entry).entry_id
        )}_{description.key}"

    @property
    def is_on(self) -> bool:
        """Return True if the entity is on."""
        return self.entity_description.value_fn(self.coordinator.device)
