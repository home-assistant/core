"""Binary sensor platform support for wiffi devices."""

import logging
from pathlib import Path

from homeassistant.const import STATE_OFF, STATE_ON

from .const import DOMAIN
from .entity_base import WiffiEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up platform for a new integration.

    Called by the HA framework after async_forward_entry_setup has been called
    during initialization of a new integration (= wiffi).
    """
    stem = Path(__file__).stem  # stem = filename without py
    hass.data[DOMAIN][config_entry.entry_id].async_add_entities[
        stem
    ] = async_add_entities


class BoolEntity(WiffiEntity):
    """Entity for wiffi metrics which have a boolean value.

    Note that we don't use BinarySensorDevice but WiffiEntity instead, which is
    derived from Entity because otherwise we had to implement the stuff from
    WiffiEntity again and as BinarySensorDevice implements only the state
    property we just copied this part from BinarySensorDevice.
    """

    def __init__(self, device_id, device_info, metric):
        """Initialize the entity."""
        WiffiEntity.__init__(self, device_id, device_info, metric)
        self._value = metric.value
        self.reset_expiration_date()

    @property
    def state(self):
        """Return the state of the entity."""
        return STATE_ON if self._value else STATE_OFF

    async def update_value(self, metric):
        """Update the value of the entity.

        Called if a new message has been received from the wiffi device.
        """
        self.reset_expiration_date()
        self._value = metric.value
        if self.enabled:
            self.async_schedule_update_ha_state()
