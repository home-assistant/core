"""Support for button entities."""
from __future__ import annotations

from dataclasses import dataclass, field

from gardena_bluetooth.const import Reset
from gardena_bluetooth.parse import CharacteristicBool

from homeassistant.components.button import (
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import Coordinator, GardenaBluetoothDescriptorEntity


@dataclass
class GardenaBluetoothButtonEntityDescription(ButtonEntityDescription):
    """Description of entity."""

    char: CharacteristicBool = field(default_factory=lambda: CharacteristicBool(""))


DESCRIPTIONS = (
    GardenaBluetoothButtonEntityDescription(
        key=Reset.factory_reset.uuid,
        translation_key="factory_reset",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        char=Reset.factory_reset,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up binary sensor based on a config entry."""
    coordinator: Coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        GardenaBluetoothButton(coordinator, description)
        for description in DESCRIPTIONS
        if description.key in coordinator.characteristics
    ]
    async_add_entities(entities)


class GardenaBluetoothButton(GardenaBluetoothDescriptorEntity, ButtonEntity):
    """Representation of a binary sensor."""

    entity_description: GardenaBluetoothButtonEntityDescription

    async def async_press(self) -> None:
        """Trigger button action."""
        await self.coordinator.write(self.entity_description.char, True)
