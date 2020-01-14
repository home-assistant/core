"""Support for tracking Tesla cars."""
import logging

from homeassistant.helpers.event import async_track_utc_time_change
from homeassistant.util import slugify

from . import DOMAIN as TESLA_DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_scanner(hass, config, async_see, discovery_info=None):
    """Set up the Tesla tracker."""
    tracker = TeslaDeviceTracker(
        hass, config, async_see, hass.data[TESLA_DOMAIN]["devices"]["devices_tracker"]
    )
    await tracker.update_info()
    async_track_utc_time_change(hass, tracker.update_info, second=range(0, 60, 30))
    return True


class TeslaDeviceTracker:
    """A class representing a Tesla device."""

    def __init__(self, hass, config, see, tesla_devices):
        """Initialize the Tesla device scanner."""
        self.hass = hass
        self.see = see
        self.devices = tesla_devices

    async def update_info(self, now=None):
        """Update the device info."""
        for device in self.devices:
            await device.async_update()
            name = device.name
            _LOGGER.debug("Updating device position: %s", name)
            dev_id = slugify(device.uniq_name)
            location = device.get_location()
            if location:
                lat = location["latitude"]
                lon = location["longitude"]
                attrs = {"trackr_id": dev_id, "id": dev_id, "name": name}
                await self.see(
                    dev_id=dev_id, host_name=name, gps=(lat, lon), attributes=attrs
                )
