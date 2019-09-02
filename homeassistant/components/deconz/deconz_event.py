"""Representation of a deCONZ remote."""
from homeassistant.const import CONF_EVENT, CONF_ID
from homeassistant.core import EventOrigin, callback
from homeassistant.helpers.device_registry import CONNECTION_ZIGBEE
from homeassistant.util import slugify

from .const import _LOGGER, DOMAIN


class DeconzEvent:
    """When you want signals instead of entities.

    Stateless sensors such as remotes are expected to generate an event
    instead of a sensor entity in hass.
    """

    def __init__(self, device, gateway):
        """Register callback that will be used for signals."""
        self._device = device
        self.gateway = gateway

        self._device.register_async_callback(self.async_update_callback)

        self.event = f"deconz_{CONF_EVENT}"
        self.id = slugify(self._device.name)
        self.gateway.hass.async_create_task(self.async_update_device_registry())
        _LOGGER.debug("deCONZ event created: %s", self.id)

    @callback
    def async_will_remove_from_hass(self) -> None:
        """Disconnect event object when removed."""
        self._device.remove_callback(self.async_update_callback)
        self._device = None

    @callback
    def async_update_callback(self, force_update=False):
        """Fire the event if reason is that state is updated."""
        if "state" in self._device.changed_keys:
            data = {CONF_ID: self.id, CONF_EVENT: self._device.state}
            self.gateway.hass.bus.async_fire(self.event, data, EventOrigin.remote)

    async def async_update_device_registry(self):
        """Update device registry."""
        device_registry = (
            await self.gateway.hass.helpers.device_registry.async_get_registry()
        )

        serial = self._device.uniqueid.split("-", 1)[0]
        bridgeid = self.gateway.api.config.bridgeid

        device_registry.async_get_or_create(
            config_entry_id=self.gateway.config_entry.entry_id,
            connections={(CONNECTION_ZIGBEE, serial)},
            identifiers={(DOMAIN, serial)},
            manufacturer=self._device.manufacturer,
            model=self._device.modelid,
            name=self._device.name,
            sw_version=self._device.swversion,
            via_device=bridgeid,
        )
