"""Bosch Smart Home Controller base entity."""
import logging

from homeassistant.helpers.entity import Entity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class SHCEntity(Entity):
    """Representation of a SHC base entity."""

    def __init__(self, device, room_name: str, controller_ip: str):
        """Initialize the generic SHC device."""
        self._device = device
        self._room_name = room_name
        self._controller_ip = controller_ip

    async def async_added_to_hass(self):
        """Subscribe to SHC events."""
        await super().async_added_to_hass()

        def on_state_changed():
            self.schedule_update_ha_state()

        for service in self._device.device_services:
            service.subscribe_callback(self.entity_id, on_state_changed)

    async def async_will_remove_from_hass(self):
        """Unsubscribe from SHC events."""
        await super().async_will_remove_from_hass()
        for service in self._device.device_services:
            service.unsubscribe_callback(self.entity_id)

    @property
    def unique_id(self):
        """Return the unique ID of this binary sensor."""
        return self._device.serial

    @property
    def name(self):
        """Name of the device."""
        return self._device.name

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self._device.id)},
            "name": self.name,
            "manufacturer": self._device.manufacturer,
            "model": self._device.device_model,
            "via_device": (DOMAIN, self._controller_ip),
        }

    @property
    def available(self):
        """Return false if status is unavailable."""
        return self._device.status == "AVAILABLE"

    @property
    def should_poll(self):
        """Report polling mode. SHC Entity is communicating via long polling."""
        return False

    def update(self):
        """Trigger an update of the device."""
        self._device.update()

    @property
    def device_state_attributes(self):
        """Extend state attribute of the device."""
        state_attr = {}
        if self._room_name:
            state_attr["bosch_shc_room_name"] = self._room_name
        return state_attr
