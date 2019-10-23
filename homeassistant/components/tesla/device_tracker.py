"""Support for tracking Tesla cars."""
import logging

from homeassistant.helpers.event import async_track_utc_time_change
from homeassistant.util import slugify

from homeassistant.components.device_tracker import see as dev_see

from . import DOMAIN as TESLA_DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_scanner(hass, config, async_see, discovery_info=None):
    """Set up the Tesla tracker."""
    hass.data[TESLA_DOMAIN]["devices"]["device_tracker"] = tracker = TeslaDeviceTracker(
        hass, config, async_see, hass.data[TESLA_DOMAIN]["devices"]["devices_tracker"]
    )
    await tracker.update_info()
    async_track_utc_time_change(hass, tracker.update_info, second=range(0, 60, 30))
    return True


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up the Tesla binary_sensors by config_entry."""
    return await hass.async_add_executor_job(
        setup_scanner, hass, config_entry.data, dev_see, None
    )


async def async_unload_entry(hass, entry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading %s", hass.data[TESLA_DOMAIN]["devices"]["device_tracker"])
    hass.data[TESLA_DOMAIN]["devices"]["device_tracker"].unload()
    return True


class TeslaDeviceTracker:
    """A class representing a Tesla device."""

    def __init__(self, hass, config, see, tesla_devices):
        """Initialize the Tesla device scanner."""
        self.hass = hass
        self.see = see
        self.devices = tesla_devices
        self._listener = track_utc_time_change(
            self.hass, self.update_info, second=range(0, 60, 30)
        )

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

    async def unload(self):
        """Update the device info."""
        self.hass.async_add_executor_job(self._listener)
