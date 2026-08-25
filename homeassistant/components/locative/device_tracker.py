"""Support for the Locative platform."""

from typing import override

from homeassistant.components.device_tracker import TrackerEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TRACKER_UPDATE, LocativeConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LocativeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Configure a dispatcher connection based on a config entry."""

    @callback
    def _receive_data(device, location, location_name):
        """Receive set location."""
        if device in entry.runtime_data:
            return

        entry.runtime_data.add(device)

        async_add_entities([LocativeEntity(device, location, location_name)])

    entry.async_on_unload(async_dispatcher_connect(hass, TRACKER_UPDATE, _receive_data))


class LocativeEntity(TrackerEntity):
    """Represent a tracked device."""

    def __init__(self, device, location, location_name):
        """Set up Locative entity."""
        self._name = device
        self._attr_latitude = location[0]
        self._attr_longitude = location[1]
        self._attr_location_name = location_name
        self._unsub_dispatcher = None

    @property
    @override
    def name(self):
        """Return the name of the device."""
        return self._name

    @override
    async def async_added_to_hass(self) -> None:
        """Register state update callback."""
        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass, TRACKER_UPDATE, self._async_receive_data
        )

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Clean up after entity before removal."""
        self._unsub_dispatcher()

    @callback
    def _async_receive_data(self, device, location, location_name):
        """Update device data."""
        if device != self._name:
            return
        self._attr_location_name = location_name
        self._attr_latitude = location[0]
        self._attr_longitude = location[1]
        self.async_write_ha_state()
