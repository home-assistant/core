"""Common entities."""
from abc import ABC, abstractmethod
import logging
from typing import Optional

from pymultimatic.model import BoilerStatus, Device, SystemInfo

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class VaillantEntity(Entity, ABC):
    """Define base class for vaillant."""

    def __init__(self, domain, device_class, comp_id, comp_name, class_in_id=True):
        """Initialize entity."""
        self._device_class = device_class
        if device_class and class_in_id:
            id_format = domain + "." + DOMAIN + "_{}_" + device_class
        else:
            id_format = domain + "." + DOMAIN + "_{}"

        self.entity_id = id_format.format(slugify(comp_id)).lower()
        self._vaillant_name = comp_name
        self.hub = None
        self._unique_id = self.entity_id

    @property
    def name(self) -> Optional[str]:
        """Return the name of the entity."""
        return self._vaillant_name

    @property
    def unique_id(self) -> Optional[str]:
        """Return a unique ID."""
        return self._unique_id

    async def async_update(self):
        """Update the entity."""
        _LOGGER.debug("Time to update %s", self.entity_id)
        if not self.hub:
            self.hub = self.hass.data[DOMAIN].api
        await self.hub.update_system()

        await self.vaillant_update()

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return self._device_class

    @abstractmethod
    async def vaillant_update(self):
        """Update specific for vaillant."""

    @property
    def listening(self):
        """Return whether this entity is listening for system changes or not.

        System changes are quick mode or holiday mode.
        """
        return False

    async def async_added_to_hass(self):
        """Call when entity is added to hass."""
        self.hass.data[DOMAIN].entities.append(self)

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        self.hass.data[DOMAIN].entities.remove(self)


class VaillantBoilerEntity(Entity):
    """Base class for boiler device."""

    def __init__(self, boiler_status: BoilerStatus) -> None:
        """Initialize device."""
        self.boiler_status = boiler_status
        if self.boiler_status is not None:
            self.boiler_id = slugify(self.boiler_status.device_name)

    @property
    def device_info(self):
        """Return device specific attributes."""
        if self.boiler_status is not None:
            return {
                "identifiers": {(DOMAIN, self.boiler_id)},
                "name": self.boiler_status.device_name,
                "manufacturer": "Vaillant",
                "model": self.boiler_status.device_name,
            }
        return None

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self.boiler_status is not None:
            return {"device_id": self.boiler_id, "error": self.boiler_status.is_error}
        return None


class VaillantRoomEntity(Entity):
    """Base class for ambisense device."""

    def __init__(self, device: Device) -> None:
        """Initialize device."""
        self.device = device

    @property
    def device_info(self):
        """Return device specific attributes."""
        return {
            "identifiers": {(DOMAIN, self.device.sgtin)},
            "name": self.device.name,
            "manufacturer": "Vaillant",
            "model": self.device.device_type,
        }

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            "device_id": self.device.sgtin,
            "battery_low": self.device.battery_low,
            "connected": not self.device.radio_out_of_reach,
        }


class VaillantBoxEntity(Entity):
    """Vaillant gateway device (ex: VR920)."""

    def __init__(self, info: SystemInfo):
        """Init."""
        self.system_info = info

    @property
    def device_info(self):
        """Return device specific attributes."""
        return {
            "identifiers": {(DOMAIN, self.system_info.serial_number)},
            "connections": {(CONNECTION_NETWORK_MAC, self.system_info.mac_ethernet)},
            "name": self.system_info.gateway,
            "manufacturer": "Vaillant",
            "model": self.system_info.gateway,
            "sw_version": self.system_info.firmware,
        }

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            "serial_number": self.system_info.serial_number,
            "connected": self.system_info.is_online,
            "up_to_date": self.system_info.is_up_to_date,
        }
