"""The Honeywell Lyric integration."""

from typing import override

from aiolyric.objects.device import LyricDevice
from aiolyric.objects.location import LyricLocation
from aiolyric.objects.priority import LyricAccessory, LyricRoom

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import LyricDataUpdateCoordinator


class LyricEntity(CoordinatorEntity[LyricDataUpdateCoordinator]):
    """Defines a base Honeywell Lyric entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LyricDataUpdateCoordinator,
        location: LyricLocation,
        device: LyricDevice,
        key: str,
    ) -> None:
        """Initialize the Honeywell Lyric entity."""
        super().__init__(coordinator)
        self._key = key
        self._location = location
        self._mac_id = device.mac_id
        self._update_thermostat = coordinator.data.update_thermostat
        self._update_fan = coordinator.data.update_fan

    @property
    @override
    def unique_id(self) -> str:
        """Return the unique ID for this entity."""
        return self._key

    @property
    def location(self) -> LyricLocation:
        """Get the Lyric Location."""
        return self.coordinator.data.locations_dict[self._location.location_id]

    @property
    def device(self) -> LyricDevice:
        """Get the Lyric Device."""
        return self.location.devices_dict[self._mac_id]


def create_thermostat_device_info(device: LyricDevice) -> DeviceInfo:
    """Return the device info for a Lyric thermostat."""
    return DeviceInfo(
        identifiers={(dr.CONNECTION_NETWORK_MAC, device.mac_id)},
        connections={(dr.CONNECTION_NETWORK_MAC, device.mac_id)},
        manufacturer="Honeywell",
        model=device.device_model,
        name=f"{device.name} Thermostat",
    )


class LyricDeviceEntity(LyricEntity):
    """Defines a Honeywell Lyric device entity."""

    @property
    @override
    def device_info(self) -> DeviceInfo:
        """Return device information about this Honeywell Lyric instance."""
        return create_thermostat_device_info(self.device)


class LyricAccessoryEntity(LyricDeviceEntity):
    """Defines a Honeywell Lyric accessory entity, a sub-device of a thermostat."""

    def __init__(
        self,
        coordinator: LyricDataUpdateCoordinator,
        location: LyricLocation,
        device: LyricDevice,
        room: LyricRoom,
        accessory: LyricAccessory,
        key: str,
    ) -> None:
        """Initialize the Honeywell Lyric accessory entity."""
        super().__init__(coordinator, location, device, key)
        self._room_id = room.id
        self._accessory_id = accessory.id

    @property
    @override
    def device_info(self) -> DeviceInfo:
        """Return device information about this Honeywell Lyric instance."""
        return DeviceInfo(
            identifiers={
                (
                    f"{dr.CONNECTION_NETWORK_MAC}_room_accessory",
                    f"{self._mac_id}_room{self._room_id}_accessory{self._accessory_id}",
                )
            },
            manufacturer="Honeywell",
            model="RCHTSENSOR",
            name=f"{self.room.room_name} Sensor",
            via_device_id=dr.async_get_device_id_by_identifier(
                self.hass,
                (dr.CONNECTION_NETWORK_MAC, self._mac_id),
                config_entry_id=self.coordinator.config_entry.entry_id,
            ),
        )

    @property
    def room(self) -> LyricRoom:
        """Get the Lyric Device."""
        return self.coordinator.data.rooms_dict[self._mac_id][self._room_id]

    @property
    def accessory(self) -> LyricAccessory:
        """Get the Lyric Device."""
        return next(
            accessory
            for accessory in self.room.accessories
            if accessory.id == self._accessory_id
        )
