"""The nexia integration base entity."""

from aiopvapi.resources.shade import ATTR_TYPE

import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.entity import Entity

from .const import (
    DEVICE_FIRMWARE,
    DEVICE_MAC_ADDRESS,
    DEVICE_MODEL,
    DEVICE_NAME,
    DEVICE_SERIAL_NUMBER,
    DOMAIN,
    FIRMWARE_BUILD,
    FIRMWARE_IN_SHADE,
    FIRMWARE_REVISION,
    FIRMWARE_SUB_REVISION,
    MANUFACTURER,
)


class HDEntity(Entity):
    """Base class for hunter douglas entities."""

    def __init__(self, coordinator, device_info, unique_id):
        """Initialize the entity."""
        super().__init__()
        self._coordinator = coordinator
        self._unique_id = unique_id
        self._device_info = device_info

    @property
    def available(self):
        """Return True if entity is available."""
        return self._coordinator.last_update_success

    @property
    def unique_id(self):
        """Return the unique id."""
        return self._unique_id

    @property
    def should_poll(self):
        """Return False, updates are controlled via coordinator."""
        return False

    @property
    def device_info(self):
        """Return the device_info of the device."""
        firmware = self._device_info[DEVICE_FIRMWARE]
        sw_version = f"{firmware[FIRMWARE_REVISION]}.{firmware[FIRMWARE_SUB_REVISION]}.{firmware[FIRMWARE_BUILD]}"
        return {
            "identifiers": {(DOMAIN, self._device_info[DEVICE_SERIAL_NUMBER])},
            "connections": {
                (dr.CONNECTION_NETWORK_MAC, self._device_info[DEVICE_MAC_ADDRESS])
            },
            "name": self._device_info[DEVICE_NAME],
            "model": self._device_info[DEVICE_MODEL],
            "sw_version": sw_version,
            "manufacturer": MANUFACTURER,
        }


class ShadeEntity(HDEntity):
    """Base class for hunter douglas shade entities."""

    def __init__(self, coordinator, device_info, shade, shade_name):
        """Initialize the shade."""
        super().__init__(coordinator, device_info, shade.id)
        self._shade_name = shade_name
        self._shade = shade

    @property
    def device_info(self):
        """Return the device_info of the device."""
        firmware = self._shade.raw_data[FIRMWARE_IN_SHADE]
        sw_version = f"{firmware[FIRMWARE_REVISION]}.{firmware[FIRMWARE_SUB_REVISION]}.{firmware[FIRMWARE_BUILD]}"
        model = self._shade.raw_data[ATTR_TYPE]
        for shade in self._shade.shade_types:
            if shade.shade_type == model:
                model = shade.description
                break

        return {
            "identifiers": {(DOMAIN, self._shade.id)},
            "name": self._shade_name,
            "model": str(model),
            "sw_version": sw_version,
            "manufacturer": MANUFACTURER,
            "via_device": (DOMAIN, self._device_info[DEVICE_SERIAL_NUMBER]),
        }
