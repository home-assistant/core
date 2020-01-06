"""Support for Freebox devices (Freebox v6 and Freebox mini 4K)."""
import logging
from typing import Dict

from homeassistant.components.device_tracker import SOURCE_TYPE_ROUTER
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.typing import HomeAssistantType

from . import FreeboxDevice
from .const import DOMAIN, TRACKER_UPDATE

_LOGGER = logging.getLogger(__name__)


async def async_get_scanner(hass, config):
    """Old way of setting up the platform."""
    pass


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the device_tracker."""
    for device in hass.data[DOMAIN].devices.values():
        _LOGGER.debug("Adding device_tracker for %s", device.name)
        async_add_entities([FreeboxTrackerEntity(device)])


class FreeboxTrackerEntity(TrackerEntity):
    """Represent a tracked device."""

    def __init__(self, device: FreeboxDevice):
        """Set up the Freebox tracker entity."""
        self._device = device
        self._unsub_dispatcher = None

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._device.mac

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self._device.name

    @property
    def latitude(self):
        """Return latitude value of the device."""
        if self._device.reachable:
            return self.hass.config.latitude
        return None

    @property
    def longitude(self):
        """Return longitude value of the device."""
        if self._device.reachable:
            return self.hass.config.longitude
        return None

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    @property
    def source_type(self) -> str:
        """Return the source type of the device."""
        return SOURCE_TYPE_ROUTER

    @property
    def icon(self) -> str:
        """Return the icon."""
        return self._device.icon

    @property
    def device_state_attributes(self) -> Dict[str, any]:
        """Return the device state attributes."""
        return self._device.state_attributes

    @property
    def device_info(self) -> Dict[str, any]:
        """Return the device information."""
        return {
            "connections": {(CONNECTION_NETWORK_MAC, self._device.mac)},
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.name,
            "manufacturer": self._device.manufacturer,
        }

    async def async_added_to_hass(self):
        """Register state update callback."""
        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass, TRACKER_UPDATE, self.async_write_ha_state
        )

    async def async_will_remove_from_hass(self):
        """Clean up after entity before removal."""
        self._unsub_dispatcher()
