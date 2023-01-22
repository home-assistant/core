"""Base class for Ring entity."""
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo, Entity

from . import ATTRIBUTION, DOMAIN


class RingEntityMixin(Entity):
    """Base implementation for Ring device."""

    _attr_attribution = ATTRIBUTION
    _attr_should_poll = False

    def __init__(self, config_entry_id, device):
        """Initialize a sensor for Ring device."""
        super().__init__()
        self._config_entry_id = config_entry_id
        self._device = device
        self._attr_extra_state_attributes = {}

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.ring_objects["device_data"].async_add_listener(self._update_callback)

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect callbacks."""
        self.ring_objects["device_data"].async_remove_listener(self._update_callback)

    @callback
    def _update_callback(self) -> None:
        """Call update method."""
        self.async_write_ha_state()

    @property
    def ring_objects(self):
        """Return the Ring API objects."""
        return self.hass.data[DOMAIN][self._config_entry_id]

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.device_id)},
            manufacturer="Ring",
            model=self._device.model,
            name=self._device.name,
        )
