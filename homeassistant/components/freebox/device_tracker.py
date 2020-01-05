"""Support for Freebox devices (Freebox v6 and Freebox mini 4K)."""
import logging
from typing import Dict

from homeassistant.components.device_tracker import SOURCE_TYPE_ROUTER
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.typing import HomeAssistantType

from .const import DOMAIN, TRACKER_UPDATE

_LOGGER = logging.getLogger(__name__)


async def async_get_scanner(hass, config):
    """Old way of setting up the platform."""
    pass


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the device_tracker."""
    fbx = hass.data[DOMAIN]
    devices = await fbx.lan.get_hosts_list()

    _LOGGER.error(devices)
    for device in devices:
        _LOGGER.debug("Adding device_tracker for %s", device["primary_name"])

        async_add_entities([FreeboxTrackerEntity(device)])


class FreeboxTrackerEntity(TrackerEntity):
    """Represent a tracked device."""

    def __init__(self, device: Dict[str, any]):
        """Set up the Freebox tracker entity."""
        self._device = device
        self._unsub_dispatcher = None

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self.mac

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self._device["primary_name"]

    @property
    def latitude(self):
        """Return latitude value of the device."""
        return self.hass.config.latitude

    @property
    def longitude(self):
        """Return longitude value of the device."""
        return self.hass.config.longitude

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
        return icon_for_freebox_device(self._device)

    @property
    def device_info(self) -> Dict[str, any]:
        """Return the device information."""
        return {
            "connections": {(CONNECTION_NETWORK_MAC, self.mac)},
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.name,
            "manufacturer": self._device["vendor_name"],
        }

    @property
    def mac(self) -> str:
        """Return the MAC address."""
        return self._device["l2ident"]["id"]

    async def async_added_to_hass(self):
        """Register state update callback."""
        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass, TRACKER_UPDATE, self.async_write_ha_state
        )

    async def async_will_remove_from_hass(self):
        """Clean up after entity before removal."""
        self._unsub_dispatcher()


def icon_for_freebox_device(device) -> str:
    """Return a battery icon valid identifier."""
    switcher = {
        "freebox_player": "mdi:",
        "laptop": "mdi:",
        "multimedia_device": "mdi:",
        "nas": "mdi:",
        "networking_device": "mdi:",
        "other": "mdi:",
        "printer": "mdi:",
        "smartphone": "mdi:",
        "television": "mdi:",
        "vg_console": "mdi:",
        "workstation": "mdi:",
    }

    return switcher.get(device["host_type"], "mdi:")
