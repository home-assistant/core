"""Base class for deCONZ devices."""
from homeassistant.core import callback
from homeassistant.helpers.device_registry import CONNECTION_ZIGBEE
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN as DECONZ_DOMAIN


class DeconzDevice(Entity):
    """Representation of a deCONZ device."""

    def __init__(self, device, gateway):
        """Set up device and add update callback to get data from websocket."""
        self._device = device
        self.gateway = gateway
        self.unsub_dispatcher = None

    async def async_added_to_hass(self):
        """Subscribe to device events."""
        self._device.register_async_callback(self.async_update_callback)
        self.gateway.deconz_ids[self.entity_id] = self._device.deconz_id
        self.unsub_dispatcher = async_dispatcher_connect(
            self.hass, self.gateway.event_reachable,
            self.async_update_callback)

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect device object when removed."""
        self._device.remove_callback(self.async_update_callback)
        del self.gateway.deconz_ids[self.entity_id]
        self.unsub_dispatcher()

    @callback
    def async_update_callback(self, reason):
        """Update the device's state."""
        self.async_schedule_update_ha_state()

    @property
    def name(self):
        """Return the name of the device."""
        return self._device.name

    @property
    def unique_id(self):
        """Return a unique identifier for this device."""
        return self._device.uniqueid

    @property
    def available(self):
        """Return True if device is available."""
        return self.gateway.available and self._device.reachable

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def device_info(self):
        """Return a device description for device registry."""
        if (self._device.uniqueid is None or
                self._device.uniqueid.count(':') != 7):
            return None
        serial = self._device.uniqueid.split('-', 1)[0]
        bridgeid = self.gateway.api.config.bridgeid
        return {
            'connections': {(CONNECTION_ZIGBEE, serial)},
            'identifiers': {(DECONZ_DOMAIN, serial)},
            'manufacturer': self._device.manufacturer,
            'model': self._device.modelid,
            'name': self._device.name,
            'sw_version': self._device.swversion,
            'via_hub': (DECONZ_DOMAIN, bridgeid),
        }
