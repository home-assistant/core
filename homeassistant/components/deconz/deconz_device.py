"""Base class for deCONZ devices."""
from homeassistant.core import callback
from homeassistant.helpers.device_registry import CONNECTION_ZIGBEE
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN as DECONZ_DOMAIN


class DeconzBase:
    """Common base for deconz entities and events."""

    def __init__(self, device, gateway):
        """Set up device and add update callback to get data from websocket."""
        self._device = device
        self.gateway = gateway

    @property
    def unique_id(self):
        """Return a unique identifier for this device."""
        return self._device.uniqueid

    @property
    def serial(self):
        """Return a serial number for this device."""
        if self._device.uniqueid is None or self._device.uniqueid.count(":") != 7:
            return None

        return self._device.uniqueid.split("-", 1)[0]

    @property
    def device_info(self):
        """Return a device description for device registry."""
        if self.serial is None:
            return None

        return {
            "connections": {(CONNECTION_ZIGBEE, self.serial)},
            "identifiers": {(DECONZ_DOMAIN, self.serial)},
            "manufacturer": self._device.manufacturer,
            "model": self._device.modelid,
            "name": self._device.name,
            "sw_version": self._device.swversion,
            "via_device": (DECONZ_DOMAIN, self.gateway.api.config.bridgeid),
        }


class DeconzDevice(DeconzBase, Entity):
    """Representation of a deCONZ device."""

    _attr_should_poll = False

    TYPE = ""

    def __init__(self, device, gateway):
        """Set up device and add update callback to get data from websocket."""
        super().__init__(device, gateway)
        self.gateway.entities[self.TYPE].add(self.unique_id)

        self._attr_name = self._device.name

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry.

        Daylight is a virtual sensor from deCONZ that should never be enabled by default.
        """
        return self._device.type != "Daylight"

    async def async_added_to_hass(self):
        """Subscribe to device events."""
        self._device.register_callback(self.async_update_callback)
        self.gateway.deconz_ids[self.entity_id] = self._device.deconz_id
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self.gateway.signal_reachable, self.async_update_callback
            )
        )

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect device object when removed."""
        self._device.remove_callback(self.async_update_callback)
        del self.gateway.deconz_ids[self.entity_id]
        self.gateway.entities[self.TYPE].remove(self.unique_id)

    @callback
    def async_update_callback(self, force_update=False):
        """Update the device's state."""
        if not force_update and self.gateway.ignore_state_updates:
            return

        self.async_write_ha_state()

    @property
    def available(self):
        """Return True if device is available."""
        return self.gateway.available and self._device.reachable
