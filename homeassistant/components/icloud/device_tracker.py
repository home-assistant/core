"""Support for tracking for iCloud devices."""
import logging

from homeassistant.components.device_tracker.const import ENTITY_ID_FORMAT
from homeassistant.helpers.dispatcher import dispatcher_connect

from . import IcloudDevice
from .const import DATA_ICLOUD, SIGNAL_UPDATE_ICLOUD

_LOGGER = logging.getLogger(__name__)


def setup_scanner(hass, config, see, discovery_info=None):
    """Set up the iCloud device tracker."""
    if discovery_info is None:
        return False

    def see_device():
        """Handle the reporting of the iCloud device position."""
        for icloud_account in hass.data[DATA_ICLOUD]:
            for devicename, device in icloud_account.devices.items():

                # An entity will not be created by see() when track=false in
                # 'known_devices.yaml', but we need to see() it at least once
                entity = hass.states.get(ENTITY_ID_FORMAT.format(devicename))
                if entity is None and device.seen:
                    continue

                if device.location is None:
                    _LOGGER.debug("No position found for device %s",
                                  devicename)
                    continue

                _LOGGER.debug("Updating device_tracker for %s", devicename)

                see(dev_id=devicename,
                    host_name=device.name,
                    gps=(
                        device.location['latitude'],
                        device.location['longitude']
                    ),
                    gps_accuracy=device.location['horizontalAccuracy'],
                    attributes=device.attributes,
                    icon=icon_for_icloud_device(device),
                    battery=device.battery_level)
                device.set_seen(True)

    dispatcher_connect(hass, SIGNAL_UPDATE_ICLOUD, see_device)

    return True


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
