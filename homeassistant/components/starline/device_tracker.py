from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.components.device_tracker.const import SOURCE_TYPE_GPS
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up StarLine entry."""
    api = hass.data[DOMAIN]
    entities = []
    for device_id, device in api.devices.items():
        entities.append(StarlineDeviceTracker(api, device))
    async_add_entities(entities)
    return True


class StarlineDeviceTracker(TrackerEntity, RestoreEntity):
    """StarLine device tracker."""
    def __init__(self, api, device):
        """Set up StarLine entity."""
        self._api = api
        self._device = device

    @property
    def unique_id(self):
        """Return the unique ID."""
        return f"starline-location-{str(self._device.device_id)}"

    @property
    def battery_level(self):
        """Return the battery level of the device."""
        return self._device.battery_level

    @property
    def device_state_attributes(self):
        """Return device specific attributes."""
        return self._device.gps_attrs

    @property
    def location_accuracy(self):
        """Return the gps accuracy of the device."""
        return self._device.position["r"] if "r" in self._device.position else 0

    @property
    def latitude(self):
        """Return latitude value of the device."""
        return self._device.position["x"]

    @property
    def longitude(self):
        """Return longitude value of the device."""
        return self._device.position["y"]

    @property
    def name(self):
        """Return the name of the device."""
        return f"{self._device.name} Location"

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def source_type(self):
        """Return the source type, eg gps or router, of the device."""
        return SOURCE_TYPE_GPS

    @property
    def device_info(self):
        """Return the device info."""
        return self._device.device_info

    @property
    def icon(self):
        return "mdi:car"

    def update(self):
        """Mark the device as seen."""
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Call when entity about to be added to Home Assistant."""
        await super().async_added_to_hass()
        self._api.add_update_listener(self.update)
