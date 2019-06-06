"""Support for tracking Tesla cars."""
import logging

from homeassistant.helpers.event import track_utc_time_change
from homeassistant.util import slugify

from . import DOMAIN as TESLA_DOMAIN

_LOGGER = logging.getLogger(__name__)


def setup_scanner(hass, config, see, discovery_info=None):
    """Set up the Tesla tracker."""
    TeslaDeviceTracker(
        hass, config, see,
        hass.data[TESLA_DOMAIN]['devices']['devices_tracker'])
    return True


class TeslaDeviceTracker:
    """A class representing a Tesla device."""

    def __init__(self, hass, config, see, tesla_devices):
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
            _LOGGER.debug("Updating device position: %s", name)
            dev_id = slugify(device.uniq_name)
            location = device.get_location()
            if location:
                lat = location['latitude']
                lon = location['longitude']
                attrs = {
                    'trackr_id': dev_id,
                    'id': dev_id,
                    'name': name
                }
                self.see(
                    dev_id=dev_id, host_name=name,
                    gps=(lat, lon), attributes=attrs
                )
