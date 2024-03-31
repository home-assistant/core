"""Support for binary_sensor entities."""

from __future__ import annotations

from dataclasses import dataclass, field

from gardena_bluetooth.const import Sensor, Valve
from gardena_bluetooth.parse import CharacteristicBool

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
from .coordinator import Coordinator, GardenaBluetoothDescriptorEntity


@dataclass(frozen=True)
class GardenaBluetoothBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Description of entity."""

    char: CharacteristicBool = field(default_factory=lambda: CharacteristicBool(""))

    @property
    def context(self) -> set[str]:
        """Context needed for update coordinator."""
        return {self.char.uuid}


DESCRIPTIONS = (
    GardenaBluetoothBinarySensorEntityDescription(
        key=Valve.connected_state.uuid,
        translation_key="valve_connected_state",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        char=Valve.connected_state,
    ),
    GardenaBluetoothBinarySensorEntityDescription(
        key=Sensor.connected_state.uuid,
        translation_key="sensor_connected_state",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        char=Sensor.connected_state,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up binary sensor based on a config entry."""
    coordinator: Coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        GardenaBluetoothBinarySensor(coordinator, description, description.context)
        for description in DESCRIPTIONS
        if description.key in coordinator.characteristics
    ]
    async_add_entities(entities)


class GardenaBluetoothBinarySensor(
    GardenaBluetoothDescriptorEntity, BinarySensorEntity
):
    """Representation of a binary sensor."""

    entity_description: GardenaBluetoothBinarySensorEntityDescription

    def _handle_coordinator_update(self) -> None:
        char = self.entity_description.char
        self._attr_is_on = self.coordinator.get_cached(char)
        super()._handle_coordinator_update()
