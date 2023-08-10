"""The DoorBird integration base entity."""

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import (
    DOORBIRD_INFO_KEY_BUILD_NUMBER,
    DOORBIRD_INFO_KEY_DEVICE_TYPE,
    DOORBIRD_INFO_KEY_FIRMWARE,
    MANUFACTURER,
)
from .util import get_mac_address_from_doorstation_info


class DoorBirdEntity(Entity):
    """Base class for doorbird entities."""

    _attr_has_entity_name = True

    def __init__(self, doorstation, doorstation_info):
        """Initialize the entity."""
        super().__init__()
        self._doorstation = doorstation
        self._mac_addr = get_mac_address_from_doorstation_info(doorstation_info)

        firmware = doorstation_info[DOORBIRD_INFO_KEY_FIRMWARE]
        firmware_build = doorstation_info[DOORBIRD_INFO_KEY_BUILD_NUMBER]
        self._attr_device_info = DeviceInfo(
            configuration_url="https://webadmin.doorbird.com/",
            connections={(dr.CONNECTION_NETWORK_MAC, self._mac_addr)},
            manufacturer=MANUFACTURER,
            model=doorstation_info[DOORBIRD_INFO_KEY_DEVICE_TYPE],
            name=self._doorstation.name,
            sw_version=f"{firmware} {firmware_build}",
        )
