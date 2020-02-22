"""Support for tracking for iCloud devices."""
import logging
from typing import Dict

from homeassistant.components.device_tracker import SOURCE_TYPE_GPS
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.typing import HomeAssistantType

from .account import IcloudDevice
from .const import (
    DEVICE_LOCATION_HORIZONTAL_ACCURACY,
    DEVICE_LOCATION_LATITUDE,
    DEVICE_LOCATION_LONGITUDE,
    DOMAIN,
    SERVICE_UPDATE,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_scanner(
    hass: HomeAssistantType, config, see, discovery_info=None
):
    """Old way of setting up the iCloud tracker."""
    pass


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
):
    """Configure a dispatcher connection based on a config entry."""
    username = entry.data[CONF_USERNAME]

    for device in hass.data[DOMAIN][username].devices.values():
        if device.location is None:
            _LOGGER.debug("No position found for %s", device.name)
            continue

        _LOGGER.debug("Adding device_tracker for %s", device.name)

        async_add_entities([IcloudTrackerEntity(device)])


class IcloudTrackerEntity(TrackerEntity):
    """Represent a tracked device."""

    def __init__(self, device: IcloudDevice):
        """Set up the iCloud tracker entity."""
        self._device = device
        self._unsub_dispatcher = None

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._device.unique_id

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self._device.name

    @property
    def location_accuracy(self):
        """Return the location accuracy of the device."""
        return self._device.location[DEVICE_LOCATION_HORIZONTAL_ACCURACY]

    @property
    def latitude(self):
        """Return latitude value of the device."""
        return self._device.location[DEVICE_LOCATION_LATITUDE]

    @property
    def longitude(self):
        """Return longitude value of the device."""
        return self._device.location[DEVICE_LOCATION_LONGITUDE]

    @property
    def battery_level(self) -> int:
        """Return the battery level of the device."""
        return self._device.battery_level

    @property
    def source_type(self) -> str:
        """Return the source type, eg gps or router, of the device."""
        return SOURCE_TYPE_GPS

    @property
    def icon(self) -> str:
        """Return the icon."""
        return icon_for_icloud_device(self._device)

    @property
    def device_state_attributes(self) -> Dict[str, any]:
        """Return the device state attributes."""
        return self._device.state_attributes

    @property
    def device_info(self) -> Dict[str, any]:
        """Return the device information."""
        return {
            "identifiers": {(DOMAIN, self._device.unique_id)},
            "name": self._device.name,
            "manufacturer": "Apple",
            "model": self._device.device_model,
        }

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    async def async_added_to_hass(self):
        """Register state update callback."""
        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass, SERVICE_UPDATE, self.async_write_ha_state
        )

    async def async_will_remove_from_hass(self):
        """Clean up after entity before removal."""
        self._unsub_dispatcher()


def icon_for_icloud_device(icloud_device: IcloudDevice) -> str:
    """Return a battery icon valid identifier."""
    switcher = {
        "iPad": "mdi:tablet-ipad",
        "iPhone": "mdi:cellphone-iphone",
        "iPod": "mdi:ipod",
        "iMac": "mdi:desktop-mac",
        "MacBookPro": "mdi:laptop-mac",
    }

    return switcher.get(icloud_device.device_class, "mdi:cellphone-link")
