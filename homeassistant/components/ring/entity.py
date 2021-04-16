"""Base class for Ring entity."""
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import callback

from . import ATTRIBUTION, DOMAIN


class RingEntityMixin:
    """Base implementation for Ring device."""

    def __init__(self, config_entry_id, device):
        """Initialize a sensor for Ring device."""
        super().__init__()
        self._config_entry_id = config_entry_id
        self._device = device

    async def async_added_to_hass(self):
        """Register callbacks."""
        self.ring_objects["device_data"].async_add_listener(self._update_callback)

    async def async_will_remove_from_hass(self):
        """Disconnect callbacks."""
        self.ring_objects["device_data"].async_remove_listener(self._update_callback)

    @callback
    def _update_callback(self):
        """Call update method."""
        self.async_write_ha_state()

    @property
    def ring_objects(self):
        """Return the Ring API objects."""
        return self.hass.data[DOMAIN][self._config_entry_id]

    @property
    def should_poll(self):
        """Return False, updates are controlled via the hub."""
        return False

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {ATTR_ATTRIBUTION: ATTRIBUTION}

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._device.device_id)},
            "name": self._device.name,
            "model": self._device.model,
            "manufacturer": "Ring",
        }
