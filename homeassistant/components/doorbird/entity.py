"""The DoorBird integration base entity."""

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import (
    DOORBIRD_INFO_KEY_BUILD_NUMBER,
    DOORBIRD_INFO_KEY_DEVICE_TYPE,
    DOORBIRD_INFO_KEY_FIRMWARE,
    MANUFACTURER,
)
from .models import DoorBirdData
from .util import get_mac_address_from_door_station_info


class DoorBirdEntity(Entity):
    """Base class for doorbird entities."""

    _attr_has_entity_name = True

    def __init__(self, door_bird_data: DoorBirdData) -> None:
        """Initialize the entity."""
        super().__init__()
        self._door_bird_data = door_bird_data
        self._door_station = door_bird_data.door_station
        door_station_info = door_bird_data.door_station_info
        self._mac_addr = get_mac_address_from_door_station_info(door_station_info)
        firmware = door_station_info[DOORBIRD_INFO_KEY_FIRMWARE]
        firmware_build = door_station_info[DOORBIRD_INFO_KEY_BUILD_NUMBER]
        self._attr_device_info = DeviceInfo(
            configuration_url="https://webadmin.doorbird.com/",
            connections={(dr.CONNECTION_NETWORK_MAC, self._mac_addr)},
            manufacturer=MANUFACTURER,
            model=door_station_info[DOORBIRD_INFO_KEY_DEVICE_TYPE],
            name=self._door_station.name,
            sw_version=f"{firmware} {firmware_build}",
        )
