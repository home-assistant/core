"""Base class for UniFi Network entities."""
import logging
from typing import Any

from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)


class UniFiBase(Entity):
    """UniFi entity base class."""

    DOMAIN = ""
    TYPE = ""

    def __init__(self, item, controller) -> None:
        """Set up UniFi Network entity base.

        Register mac to controller entities to cover disabled entities.
        """
        self._item = item
        self.controller = controller
        self.controller.entities[self.DOMAIN][self.TYPE].add(self.key)

    @property
    def key(self) -> Any:
        """Return item key."""
        return self._item.mac

    async def async_added_to_hass(self) -> None:
        """Entity created."""
        _LOGGER.debug(
            "New %s entity %s (%s)",
            self.TYPE,
            self.entity_id,
            self.key,
        )
        for signal, method in (
            (self.controller.signal_reachable, self.async_signal_reachable_callback),
            (self.controller.signal_options_update, self.options_updated),
            (self.controller.signal_remove, self.remove_item),
        ):
            self.async_on_remove(async_dispatcher_connect(self.hass, signal, method))
        self._item.register_callback(self.async_update_callback)

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect object when removed."""
        _LOGGER.debug(
            "Removing %s entity %s (%s)",
            self.TYPE,
            self.entity_id,
            self.key,
        )
        self._item.remove_callback(self.async_update_callback)
        self.controller.entities[self.DOMAIN][self.TYPE].remove(self.key)

    @callback
    def async_signal_reachable_callback(self) -> None:
        """Call when controller connection state change."""
        self.async_update_callback()

    @callback
    def async_update_callback(self) -> None:
        """Update the entity's state."""
        _LOGGER.debug(
            "Updating %s entity %s (%s)",
            self.TYPE,
            self.entity_id,
            self.key,
        )
        self.async_write_ha_state()

    async def options_updated(self) -> None:
        """Config entry options are updated, remove entity if option is disabled."""
        raise NotImplementedError

    async def remove_item(self, keys: set) -> None:
        """Remove entity if key is part of set."""
        if self.key not in keys:
            return

        if self.registry_entry:
            er.async_get(self.hass).async_remove(self.entity_id)
        else:
            await self.async_remove(force_remove=True)

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False
