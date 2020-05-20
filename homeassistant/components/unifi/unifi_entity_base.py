"""Base class for UniFi entities."""
import logging

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_registry import async_entries_for_device

LOGGER = logging.getLogger(__name__)


class UniFiBase(Entity):
    """UniFi entity base class."""

    DOMAIN = ""
    TYPE = ""

    def __init__(self, item, controller) -> None:
        """Set up UniFi entity base.

        Register mac to controller entities to cover disabled entities.
        """
        self._item = item
        self.controller = controller
        self.controller.entities[self.DOMAIN][self.TYPE].add(item.mac)

    async def async_added_to_hass(self) -> None:
        """Entity created."""
        LOGGER.debug("New %s entity %s (%s)", self.TYPE, self.entity_id, self._item.mac)
        for signal, method in (
            (self.controller.signal_reachable, self.async_update_callback),
            (self.controller.signal_options_update, self.options_updated),
            (self.controller.signal_remove, self.remove_item),
        ):
            self.async_on_remove(async_dispatcher_connect(self.hass, signal, method))
        self._item.register_callback(self.async_update_callback)

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect object when removed."""
        LOGGER.debug(
            "Removing %s entity %s (%s)", self.TYPE, self.entity_id, self._item.mac
        )
        self._item.remove_callback(self.async_update_callback)
        self.controller.entities[self.DOMAIN][self.TYPE].remove(self._item.mac)

    @callback
    def async_update_callback(self) -> None:
        """Update the entity's state."""
        LOGGER.debug(
            "Updating %s entity %s (%s)", self.TYPE, self.entity_id, self._item.mac
        )
        self.async_write_ha_state()

    async def options_updated(self) -> None:
        """Config entry options are updated, remove entity if option is disabled."""
        raise NotImplementedError

    async def remove_item(self, mac_addresses: set) -> None:
        """Remove entity if MAC is part of set.

        Remove entity if no entry in entity registry exist.
        Remove entity registry entry if no entry in device registry exist.
        Remove device registry entry if there is only one linked entity (this entity).
        Remove entity registry entry if there are more than one entity linked to the device registry entry.
        """
        if self._item.mac not in mac_addresses:
            return

        entity_registry = await self.hass.helpers.entity_registry.async_get_registry()
        entity_entry = entity_registry.async_get(self.entity_id)
        if not entity_entry:
            await self.async_remove()
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

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False
