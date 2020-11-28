"""Support for interface with a Gree climate systems."""
import logging
from typing import Optional

from homeassistant.components.switch import DEVICE_CLASS_SWITCH, SwitchEntity
from homeassistant.core import callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import COORDINATORS, DISPATCH_DEVICE_DISCOVERED, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Gree HVAC device from a config entry."""

    @callback
    def init_device(coordinator):
        """Register the device."""
        async_add_entities([GreeSwitchEntity(coordinator)])

    for coordo in hass.data[DOMAIN][COORDINATORS]:
        init_device(coordo)

    async_dispatcher_connect(hass, DISPATCH_DEVICE_DISCOVERED, init_device)


class GreeSwitchEntity(CoordinatorEntity, SwitchEntity):
    """Representation of a Gree HVAC device."""

    def __init__(self, coordo):
        """Initialize the Gree device."""
        super().__init__(coordo)
        self._coordo = coordo
        self._name = coordo.device.device_info.name + " Panel Light"
        self._mac = coordo.device.device_info.mac

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return a unique id for the device."""
        return f"{self._mac}-panel-light"

    @property
    def icon(self) -> Optional[str]:
        """Return the icon for the device."""
        return "mdi:lightbulb"

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
        return self._coordo.device.light

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        self._coordo.device.light = True
        await self._coordo.push_state_update()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        self._coordo.device.light = False
        await self._coordo.push_state_update()
        self.async_write_ha_state()
