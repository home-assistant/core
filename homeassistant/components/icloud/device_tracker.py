"""Support for tracking for iCloud devices."""
import logging

from homeassistant.core import callback
from homeassistant.components.device_tracker import SOURCE_TYPE_GPS
from homeassistant.const import CONF_USERNAME
from homeassistant.components.device_tracker.const import ENTITY_ID_FORMAT
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import IcloudDevice
from .const import DOMAIN, TRACKER_UPDATE

_LOGGER = logging.getLogger(__name__)


async def async_setup_scanner(hass, config, see, discovery_info=None):
    """Old way of setting up the iCloud tracker."""
    pass


async def async_setup_entry(hass, entry, async_add_entities):
    """Configure a dispatcher connection based on a config entry."""
    username = entry.data[CONF_USERNAME]

    for device in hass.data[DOMAIN][username].devices.values():

        # An entity will not be created by see() when track=false in
        # 'known_devices.yaml', but we need to see() it at least once
        entity = hass.states.get(ENTITY_ID_FORMAT.format(device.dev_id))
        if entity is None and device.seen:
            continue

        if device.location is None:
            _LOGGER.debug("No position found for device %s", device.name)
            continue

        _LOGGER.debug("Updating device_tracker for %s", device.name)

        async_add_entities([IcloudTrackerEntity(device)])
        device.set_seen(True)

    return True


class IcloudTrackerEntity(TrackerEntity):
    """Represent a tracked device."""

    def __init__(self, device: IcloudDevice):
        """Set up the iCloud tracker entity."""
        self._device = device
        self._unsub_dispatcher = None

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"{self._device.unique_id}_tracker"

    @property
    def name(self):
        """Return the name of the device."""
        return self._device.name

    @property
    def location_accuracy(self):
        """Return the location accuracy of the device."""
        return self._device.location["horizontalAccuracy"]

    @property
    def latitude(self):
        """Return latitude value of the device."""
        return self._device.location["latitude"]

    @property
    def longitude(self):
        """Return longitude value of the device."""
        return self._device.location["longitude"]

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def battery_level(self):
        """Return the battery level of the device."""
        return self._device.battery_level

    @property
    def source_type(self):
        """Return the source type, eg gps or router, of the device."""
        return SOURCE_TYPE_GPS

    @property
    def icon(self):
        """Return the icon."""
        return icon_for_icloud_device(self._device)

    @property
    def state_attributes(self):
        """Return the device state attributes."""
        return self._device.state_attributes

    async def async_added_to_hass(self):
        """Register state update callback."""
        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass, TRACKER_UPDATE, self._async_receive_data
        )

    async def async_will_remove_from_hass(self):
        """Clean up after entity before removal."""
        self._unsub_dispatcher()

    @callback
    def _async_receive_data(self, device: IcloudDevice):
        """Update device data."""
        if device.unique_id != self._device.unique_id:
            return

        self._device = device
        self.async_write_ha_state()


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
