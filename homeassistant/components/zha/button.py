"""Support for ZHA button."""

from __future__ import annotations

import functools
import logging

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import ZHAEntity
from .helpers import (
    SIGNAL_ADD_ENTITIES,
    EntityData,
    async_add_entities as zha_async_add_entities,
    convert_zha_error_to_ha_error,
    get_zha_data,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Zigbee Home Automation button from config entry."""
    zha_data = get_zha_data(hass)
    entities_to_create = zha_data.platforms[Platform.BUTTON]

    unsub = async_dispatcher_connect(
        hass,
        SIGNAL_ADD_ENTITIES,
        functools.partial(
            zha_async_add_entities, async_add_entities, ZHAButton, entities_to_create
        ),
    )
    config_entry.async_on_unload(unsub)


class ZHAButton(ZHAEntity, ButtonEntity):
    """Defines a ZHA button."""

    def __init__(self, entity_data: EntityData) -> None:
        """Initialize the ZHA binary sensor."""
        super().__init__(entity_data)
        if self.entity_data.entity.info_object.device_class is not None:
            self._attr_device_class = ButtonDeviceClass(
                self.entity_data.entity.info_object.device_class
            )

    @convert_zha_error_to_ha_error
    async def async_press(self) -> None:
        """Send out a update command."""
        await self.entity_data.entity.async_press()
