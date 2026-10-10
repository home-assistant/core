"""Base class for Acmeda Roller Blinds."""

from typing import override

import aiopulse

from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr, entity

from .const import DOMAIN, LOGGER


class AcmedaEntity(entity.Entity):
    """Base representation of an Acmeda roller."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, roller: aiopulse.Roller) -> None:
        """Initialize the roller."""
        self.roller = roller

    @override
    async def async_added_to_hass(self) -> None:
        """Entity has been added to hass."""
        self.roller.callback_subscribe(self.notify_update)

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Entity being removed from hass."""
        self.roller.callback_unsubscribe(self.notify_update)

    def notify_update(self) -> None:
        """Schedule update on the event loop from aiopulse thread."""
        self.hass.loop.call_soon_threadsafe(self._handle_update)

    @callback
    def _handle_update(self) -> None:
        """Handle update on the event loop."""
        LOGGER.debug("Device update notification received: %s", self.name)
        self.async_write_ha_state()

    @property
    @override
    def unique_id(self) -> str:
        """Return the unique ID of this roller."""
        return str(self.roller.id)

    @property
    def device_id(self) -> str:
        """Return the ID of this roller."""
        return str(self.roller.id)

    @property
    @override
    def device_info(self) -> dr.DeviceInfo:
        """Return the device info."""
        return dr.DeviceInfo(
            identifiers={(DOMAIN, self.unique_id)},
            manufacturer="Rollease Acmeda",
            name=self.roller.name,
        )
