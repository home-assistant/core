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
    def device_id(self):
        """Return the ID of this binary sensor."""
        return self._device.id

    @property
    def root_device(self):
        """Return the root device id."""
        return self._device.root_device_id

    @property
    def name(self):
        """Name of the device."""
        return self._device.name

    @property
    def manufacturer(self):
        """Manufacturer of the device."""
        return self._device.manufacturer

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self.device_id)},
            "name": self.name,
            "manufacturer": self.manufacturer,
            "model": self._device.device_model,
            "sw_version": "",
            "via_device": (DOMAIN, self._controller_ip),
        }

    @property
    def available(self):
        """Return false if status is unavailable."""
        if self._device.status == "AVAILABLE":
            return True
        return False

    @property
    def should_poll(self):
        """Report polling mode. SHC Entity is communicating via long polling."""
        return False

    def update(self):
        """Trigger an update of the device."""
        self._device.update()

    @property
    def state_attributes(self):
        """Extend state attribute of the device."""
        state_attr = super().state_attributes
        if state_attr is None:
            state_attr = dict()
        if self._room_name:
            state_attr["boschshc_room_name"] = self._room_name
        return state_attr
