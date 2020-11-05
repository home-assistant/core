"""Support for interface with a Gree climate systems."""
import logging

from homeassistant.components.switch import (
    DEVICE_CLASS_SWITCH,
    DOMAIN as SWITCH_DOMAIN,
    SwitchEntity,
)
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .bridge import DeviceDataUpdateCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Gree HVAC device from a config entry."""
    async_add_entities(
        GreeSwitchEntity(device) for device in hass.data[DOMAIN].pop(SWITCH_DOMAIN)
    )


class GreeSwitchEntity(CoordinatorEntity, SwitchEntity):
    """Representation of a Gree HVAC device."""

    def __init__(self, device):
        """Initialize the Gree device."""
        super().__init__(device)
        self._device = device
        self._name = device.device_info.name + " Panel Light"
        self._mac = device.device_info.mac

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return a unique id for the device."""
        return self._mac

    @property
    def device_info(self):
        """Return device specific attributes."""
        return {
            "name": self._name,
            "identifiers": {(DOMAIN, self._mac)},
            "manufacturer": "Gree",
            "connections": {(CONNECTION_NETWORK_MAC, self._mac)},
        }

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS_SWITCH

    @property
    def is_on(self) -> bool:
        """Return if the light is turned on."""
        return self._device.light

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        self._device.light = True
        await self._device.push_state_update()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        self._device.light = False
        await self._device.push_state_update()
        self.async_write_ha_state()
