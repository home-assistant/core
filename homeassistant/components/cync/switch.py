"""Support for Cync switch entities."""

from typing import Any

from pycync import CyncDevice
from pycync.devices.device_types import DeviceType

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import CyncConfigEntry
from .entity import CyncBaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CyncConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Cync switches from a config entry."""

    coordinator = entry.runtime_data
    cync = coordinator.cync

    entities_to_add = []

    for home in cync.get_homes():
        for room in home.rooms:
            room_plugs = [
                CyncSwitchEntity(device, coordinator, room.name)
                for device in room.devices
                if device.device_type == DeviceType.PLUG
            ]
            entities_to_add.extend(room_plugs)

            group_plugs = [
                CyncSwitchEntity(device, coordinator, room.name)
                for group in room.groups
                for device in group.devices
                if device.device_type == DeviceType.PLUG
            ]
            entities_to_add.extend(group_plugs)

    async_add_entities(entities_to_add)


class CyncSwitchEntity(CyncBaseEntity, SwitchEntity):
    """Representation of a Cync plug."""

    _attr_device_class = SwitchDeviceClass.OUTLET
    _attr_name = None

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the plug."""
        await self._device.turn_on()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the plug."""
        await self._device.turn_off()

    @property
    def _device(self) -> CyncDevice:
        """Fetch the reference to the backing Cync device for this plug."""
        return self.coordinator.data[self._cync_device_id]
