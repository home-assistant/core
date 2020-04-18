"""Base class for UniFi entities."""

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity


class UniFiBase(Entity):
    """UniFi entity base class."""

    TYPE = ""

    def __init__(self, controller) -> None:
        """Set up UniFi entity base."""
        self.controller = controller

    @property
    def mac(self):
        """Return MAC of entity."""
        raise NotImplementedError

    async def async_added_to_hass(self) -> None:
        """Entity created."""
        self.controller.entities[self.platform.domain][self.TYPE].add(self.mac)
        for signal, method in (
            (self.controller.signal_reachable, self.async_update_callback),
            (self.controller.signal_options_update, self.options_updated),
            (self.controller.signal_remove, self.remove_item),
        ):
            self.async_on_remove(async_dispatcher_connect(self.hass, signal, method))

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect object when removed."""
        self.controller.entities[self.platform.domain][self.TYPE].remove(self.mac)

    @callback
    def async_update_callback(self):
        """Update the entity's state."""
        raise NotImplementedError

    async def options_updated(self) -> None:
        """Config entry options are updated, remove entity if option is disabled."""
        raise NotImplementedError

    async def remove_item(self, mac_addresses: set) -> None:
        """Remove entity if MAC is part of set."""
        if self.mac in mac_addresses:
            await self.async_remove()

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return True
