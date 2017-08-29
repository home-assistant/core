"""
Support for the Tesla platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.tesla/
"""
import logging
from homeassistant.helpers.event import track_utc_time_change
from homeassistant.util import slugify
from homeassistant.components.tesla import TESLA_DEVICES
DEPENDENCIES = ['tesla']
_LOGGER = logging.getLogger(__name__)


def setup_scanner(hass, config, see, discovery_info=None):
    """Set up the Tesla tracker."""
    TeslaDeviceTracker(hass, config, see, TESLA_DEVICES['devices_tracker'])
    return True


class TeslaDeviceTracker(object):
    """A class representing a Tesla device."""

    def __init__(self, hass, config, see, tesla_devices, ):
        """Initialize the Tesla device scanner."""
        self.hass = hass
        self.see = see
        self.devices = tesla_devices
        self._update_info()

        track_utc_time_change(
            self.hass, self._update_info, second=range(0, 60, 30))

    def _update_info(self, now=None):
        """Update the device info."""
        for device in self.devices:
            device.update()
            name = device.name
            _LOGGER.debug('Updating device position:', name)
            tesla_id = slugify(device.uniq_name)
            dev_id = slugify(name)

            if dev_id is None:
                dev_id = tesla_id
            location = device.get_location()
            lat = location['latitude']
            lon = location['longitude']
            attrs = {
                'trackr_id': tesla_id,
                'id': tesla_id,
                'name': name
            }
            self.see(
                dev_id=tesla_id, host_name=name,
                gps=(lat, lon), attributes=attrs
            )
