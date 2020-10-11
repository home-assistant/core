"""Base class for KNX devices."""
from xknx.devices import Climate as XknxClimate, Device as XknxDevice

from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class KnxEntity(Entity):
    """Representation of a KNX entity."""

    def __init__(self, device: XknxDevice):
        """Set up device."""
        self._device = device

    @property
    def name(self):
        """Return the name of the KNX device."""
        return self._device.name

    @property
    def available(self):
        """Return True if entity is available."""
        return self.hass.data[DOMAIN].connected

    @property
    def should_poll(self):
        """No polling needed within KNX."""
        return False

    async def async_update(self):
        """Request a state update from KNX bus."""
        await self._device.sync()

    async def after_update_callback(self, device: XknxDevice):
        """Call after device was updated."""
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Store register state change callback."""
        self._device.register_device_updated_cb(self.after_update_callback)

        if isinstance(self._device, XknxClimate):
            self._device.mode.register_device_updated_cb(self.after_update_callback)

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect device object when removed."""
        self._device.unregister_device_updated_cb(self.after_update_callback)

        if isinstance(self._device, XknxClimate):
            self._device.mode.unregister_device_updated_cb(self.after_update_callback)
