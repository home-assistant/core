"""Base class for Netatmo entities."""
import logging
from typing import Dict, List

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_registry import async_entries_for_device

from .data_handler import NetatmoDataHandler

_LOGGER = logging.getLogger(__name__)


class NetatmoBase(Entity):
    """Netatmo entity base class."""

    DOMAIN = ""
    TYPE = ""

    def __init__(self, data_handler: NetatmoDataHandler) -> None:
        """Set up Netatmo entity base."""
        self.data_handler = data_handler
        self._data_classes: List[Dict] = []

    async def async_added_to_hass(self) -> None:
        """Entity created."""
        _LOGGER.debug("New client %s", self.entity_id)
        for data_class in self._data_classes:
            if "home_id" in data_class:
                await self.data_handler.register_data_class(
                    data_class["name"], home_id=data_class["home_id"]
                )
                signal_name = f"{data_class['name']}-{data_class['home_id']}"
            else:
                await self.data_handler.register_data_class(data_class["name"])
                signal_name = f"{data_class['name']}"

            self.data_handler.listeners.append(
                async_dispatcher_connect(
                    self.hass,
                    f"netatmo-update-{signal_name}",
                    self.async_update_callback,
                )
            )
        self.async_update_callback()

    async def async_remove(self):
        """Clean up when removing entity.

        Remove entity if no entry in entity registry exist.
        Remove entity registry entry if no entry in device registry exist.
        Remove device registry entry if there is only one linked entity (this entity).
        Remove entity registry entry if there are more than one entity linked to the
        device registry entry.
        """
        entity_registry = await self.hass.helpers.entity_registry.async_get_registry()
        entity_entry = entity_registry.async_get(self.entity_id)
        if not entity_entry:
            await super().async_remove()
            return

        device_registry = await self.hass.helpers.device_registry.async_get_registry()
        device_entry = device_registry.async_get(entity_entry.device_id)
        if not device_entry:
            entity_registry.async_remove(self.entity_id)
            return

        if len(async_entries_for_device(entity_registry, entity_entry.device_id)) == 1:
            device_registry.async_remove_device(device_entry.id)
            return

        entity_registry.async_remove(self.entity_id)

    @callback
    def async_update_callback(self):
        """Update the entity's state."""
        raise NotImplementedError

    async def options_updated(self) -> None:
        """Config entry options are updated, remove entity if option is disabled."""
        raise NotImplementedError

    async def remove_item(self, mac_addresses: set) -> None:
        """Remove entity if MAC is part of set."""
        raise NotImplementedError

    @property
    def _data(self):
        return self.data_handler.data[self._data_classes[0]["name"]]
