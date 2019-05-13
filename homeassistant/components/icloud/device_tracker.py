"""Support for tracking for iCloud devices."""
import logging

from homeassistant.helpers.dispatcher import dispatcher_connect

from . import DATA_ICLOUD, SIGNAL_UPDATE_ICLOUD, IcloudDevice

_LOGGER = logging.getLogger(__name__)


_LOGGER.info('DEVICE_TRACKER:flat')

def setup_scanner(hass, config, see, discovery_info=None):
    """Set up the iCloud device tracker."""
    _LOGGER.info('DEVICE_TRACKER:setup_scanner')
    if discovery_info is None:
        return False

    def see_device():
        """Handle the reporting of the iCloud device position."""
        _LOGGER.info('DEVICE_TRACKER:see_device')
        for accountname, icloud_account in hass.data[DATA_ICLOUD].items():
            for devicename, device in icloud_account.devices.items():
                if not device.location:
                    _LOGGER.debug("No position found for device %s",
                                  devicename)
                    return
                _LOGGER.debug("Updating device_tracker for %s", devicename)

                see(dev_id=devicename,
                    host_name=device.name,
                    gps=(
                        device.location['latitude'],
                        device.location['longitude']
                    ),
                    gps_accuracy=device.location['horizontalAccuracy'],
                    attributes=device.device_state_attributes,
                    icon=icon_for_icloud_device(device))

    dispatcher_connect(hass, SIGNAL_UPDATE_ICLOUD, see_device)

    return True

def icon_for_icloud_device(icloud_device: IcloudDevice) -> str:
    """Return a battery icon valid identifier."""
    switcher ={
        "iPad":"mdi:tablet-ipad",
        "iPhone": "mdi:cellphone-iphone",
        "iPod": "mdi:ipod",
        "iMac":"mdi:desktop-mac",
        "MacBookPro":"mdi:laptop-mac",
    }

    return switcher.get(icloud_device.device_class, "mdi:cellphone-link")
