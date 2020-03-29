"""Base class for Acmeda Roller Blinds."""
import logging

import aiopulse

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class AcmedaBase:
    """Base representation of an Acmeda roller."""

    def __init__(self, hass, roller: aiopulse.Roller, hub: aiopulse.Hub):
        """Initialize the roller."""
        self.hass = hass
        self.roller = roller
        self.hub = hub

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
            "identifiers": {(DOMAIN, self.device_id)},
            "name": self.roller.name,
            "manufacturer": "Rollease Acmeda",
            # "model": self.roller.productname or self.roller.modelid,
            # Not yet exposed as properties in aiopulse
            # "sw_version": self.roller.raw["swversion"],
            "via_device": (DOMAIN, self.hub.api.id),
        }
