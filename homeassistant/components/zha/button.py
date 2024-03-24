"""Support for ZHA button."""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import ZHAEntity
from .helpers import get_zha_data

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Zigbee Home Automation button from config entry."""
    zha_data = get_zha_data(hass)
    entities_to_create = zha_data.platforms.pop(Platform.BUTTON, [])
    entities = [ZHAButton(entity_data) for entity_data in entities_to_create]
    async_add_entities(entities)


class ZHAButton(ZHAEntity, ButtonEntity):
    """Defines a ZHA button."""

    def __init__(self, entity_data) -> None:
        """Initialize the ZHA binary sensor."""
        super().__init__(entity_data)
        if hasattr(self.entity_data.entity, "_attr_device_class"):
            self._attr_device_class = ButtonDeviceClass(
                self.entity_data.entity._attr_device_class.value
            )

    async def async_press(self) -> None:
        """Send out a update command."""
        await self.entity_data.entity.async_press()
