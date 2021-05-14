"""Bosch Smart Home Controller base entity."""
from boschshcpy.device import SHCDevice

from homeassistant.helpers.device_registry import async_get as get_dev_reg
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


async def async_remove_devices(hass, entity, entry_id):
    """Get item that is removed from session."""
    dev_registry = get_dev_reg(hass)
    device = dev_registry.async_get_device(
        identifiers={(DOMAIN, entity.device_id)}, connections=set()
    )
    if device is not None:
        dev_registry.async_update_device(device.id, remove_config_entry_id=entry_id)


class SHCEntity(Entity):
    """Representation of a SHC base entity."""

    def __init__(self, device: SHCDevice, parent_id: str, entry_id: str) -> None:
        """Initialize the generic SHC device."""
        self._device = device
        self._parent_id = parent_id
        self._entry_id = entry_id

    async def async_added_to_hass(self):
        """Subscribe to SHC events."""
        await super().async_added_to_hass()

        def on_state_changed():
            self.schedule_update_ha_state()

        def update_entity_information():
            if self._device.deleted:
                self.hass.add_job(async_remove_devices(self.hass, self, self._entry_id))
            else:
                self.schedule_update_ha_state()

        for service in self._device.device_services:
            service.subscribe_callback(self.entity_id, on_state_changed)
        self._device.subscribe_callback(self.entity_id, update_entity_information)

    async def async_will_remove_from_hass(self):
        """Unsubscribe from SHC events."""
        await super().async_will_remove_from_hass()
        for service in self._device.device_services:
            service.unsubscribe_callback(self.entity_id)
        self._device.unsubscribe_callback(self.entity_id)

    @property
    def unique_id(self):
        """Return the unique ID of the device."""
        return self._device.serial

    @property
    def name(self):
        """Name of the entity."""
        return self._device.name

    @property
    def device_id(self):
        """Device id of the entity."""
        return self._device.id

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self.device_id)},
            "name": self._device.name,
            "manufacturer": self._device.manufacturer,
            "model": self._device.device_model,
            "via_device": (
                DOMAIN,
                self._device.parent_device_id
                if self._device.parent_device_id is not None
                else self._parent_id,
            ),
        }

    @property
    def available(self):
        """Return false if status is unavailable."""
        return self._device.status == "AVAILABLE"

    @property
    def should_poll(self):
        """Report polling mode. SHC Entity is communicating via long polling."""
        return False
