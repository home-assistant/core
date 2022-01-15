"""The nexia integration base entity."""

from aiopvapi.resources.shade import ATTR_TYPE

from homeassistant.const import ATTR_MODEL, ATTR_SW_VERSION
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DEVICE_FIRMWARE,
    DEVICE_MAC_ADDRESS,
    DEVICE_MODEL,
    DEVICE_NAME,
    DEVICE_SERIAL_NUMBER,
    DOMAIN,
    FIRMWARE,
    FIRMWARE_BUILD,
    FIRMWARE_REVISION,
    FIRMWARE_SUB_REVISION,
    MANUFACTURER,
)


class HDEntity(CoordinatorEntity):
    """Base class for hunter douglas entities."""

    def __init__(self, coordinator, device_info, room_name, unique_id):
        """Initialize the entity."""
        super().__init__(coordinator)
        self._room_name = room_name
        self._unique_id = unique_id
        self._device_info = device_info

    @property
    def unique_id(self):
        """Return the unique id."""
        return self._unique_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device_info of the device."""
        firmware = self._device_info[DEVICE_FIRMWARE]
        sw_version = f"{firmware[FIRMWARE_REVISION]}.{firmware[FIRMWARE_SUB_REVISION]}.{firmware[FIRMWARE_BUILD]}"
        return DeviceInfo(
            connections={
                (dr.CONNECTION_NETWORK_MAC, self._device_info[DEVICE_MAC_ADDRESS])
            },
            identifiers={(DOMAIN, self._device_info[DEVICE_SERIAL_NUMBER])},
            manufacturer=MANUFACTURER,
            model=self._device_info[DEVICE_MODEL],
            name=self._device_info[DEVICE_NAME],
            suggested_area=self._room_name,
            sw_version=sw_version,
        )


class ShadeEntity(HDEntity):
    """Base class for hunter douglas shade entities."""

    def __init__(self, coordinator, device_info, room_name, shade, shade_name):
        """Initialize the shade."""
        super().__init__(coordinator, device_info, room_name, shade.id)
        self._shade_name = shade_name
        self._shade = shade

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device_info of the device."""

        device_info = DeviceInfo(
            identifiers={(DOMAIN, self._shade.id)},
            name=self._shade_name,
            suggested_area=self._room_name,
            manufacturer=MANUFACTURER,
            model=str(self._shade.raw_data[ATTR_TYPE]),
            via_device=(DOMAIN, self._device_info[DEVICE_SERIAL_NUMBER]),
        )

        for shade in self._shade.shade_types:
            if shade.shade_type == device_info[ATTR_MODEL]:
                device_info[ATTR_MODEL] = shade.description
                break

        if FIRMWARE not in self._shade.raw_data:
            return device_info

        firmware = self._shade.raw_data[FIRMWARE]
        sw_version = f"{firmware[FIRMWARE_REVISION]}.{firmware[FIRMWARE_SUB_REVISION]}.{firmware[FIRMWARE_BUILD]}"

        device_info[ATTR_SW_VERSION] = sw_version

        return device_info
