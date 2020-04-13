"""Base class for Acmeda Roller Blinds."""
import aiopulse

from homeassistant.core import callback
from homeassistant.helpers import entity

from .const import DOMAIN, LOGGER


class AcmedaBase(entity.Entity):
    """Base representation of an Acmeda roller."""

    def __init__(self, hass, roller: aiopulse.Roller):
        """Initialize the roller."""
        self.hass = hass
        self.roller = roller

    async def async_added_to_hass(self):
        """Entity has been added to hass."""
        self.roller.callback_subscribe(self.notify_update)

    async def async_reset(self):
        """Entity being removed from hass."""
        self.roller.callback_unsubscribe(self.notify_update)

    @callback
    def notify_update(self):
        """Write updated device state information."""
        LOGGER.debug("Device update notification received: %s", self.name)
        self.async_write_ha_state()

    @property
    def should_poll(self):
        """Report that Acmeda entities do not need polling."""
        return False

    @property
    def unique_id(self):
        """Return the unique ID of this roller."""
        return self.roller.id

    @property
    def device_id(self):
        """Return the ID of this roller."""
        return self.unique_id

    @property
    def name(self):
        """Return the name of roller."""
        return self.roller.name

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self.roller.id)},
            "name": self.roller.name,
            "manufacturer": "Rollease Acmeda",
            "via_device": (DOMAIN, self.roller.hub.id),
        }
