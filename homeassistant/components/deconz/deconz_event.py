"""Representation of a deCONZ remote."""
from homeassistant.const import CONF_EVENT, CONF_ID, CONF_UNIQUE_ID
from homeassistant.core import callback
from homeassistant.util import slugify

from .const import CONF_GESTURE, LOGGER
from .deconz_device import DeconzBase

CONF_DECONZ_EVENT = "deconz_event"


class DeconzEvent(DeconzBase):
    """When you want signals instead of entities.

    Stateless sensors such as remotes are expected to generate an event
    instead of a sensor entity in hass.
    """

    def __init__(self, device, gateway):
        """Register callback that will be used for signals."""
        super().__init__(device, gateway)

        self._device.register_callback(self.async_update_callback)

        self.device_id = None
        self.event_id = slugify(self._device.name)
        LOGGER.debug("deCONZ event created: %s", self.event_id)

    @property
    def device(self):
        """Return Event device."""
        return self._device

    @callback
    def async_will_remove_from_hass(self) -> None:
        """Disconnect event object when removed."""
        self._device.remove_callback(self.async_update_callback)
        self._device = None

    @callback
    def async_update_callback(self, force_update=False, ignore_update=False):
        """Fire the event if reason is that state is updated."""
        if ignore_update or "state" not in self._device.changed_keys:
            return

        data = {
            CONF_ID: self.event_id,
            CONF_UNIQUE_ID: self.serial,
            CONF_EVENT: self._device.state,
        }

        if self._device.gesture is not None:
            data[CONF_GESTURE] = self._device.gesture

        self.gateway.hass.bus.async_fire(CONF_DECONZ_EVENT, data)

    async def async_update_device_registry(self):
        """Update device registry."""
        device_registry = (
            await self.gateway.hass.helpers.device_registry.async_get_registry()
        )

        entry = device_registry.async_get_or_create(
            config_entry_id=self.gateway.config_entry.entry_id, **self.device_info
        )
        self.device_id = entry.id
