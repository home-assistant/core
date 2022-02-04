"""StarLine device tracker."""
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.components.device_tracker.const import SOURCE_TYPE_GPS
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .account import StarlineAccount, StarlineDevice
from .const import DOMAIN
from .entity import StarlineEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up StarLine entry."""
    account: StarlineAccount = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for device in account.api.devices.values():
        if device.support_position:
            entities.append(StarlineDeviceTracker(account, device))
    async_add_entities(entities)


class StarlineDeviceTracker(StarlineEntity, TrackerEntity, RestoreEntity):
    """StarLine device tracker."""

    def __init__(self, account: StarlineAccount, device: StarlineDevice) -> None:
        """Set up StarLine entity."""
        super().__init__(account, device, "location", "Location")

    @property
    def extra_state_attributes(self):
        """Return device specific attributes."""
        return self._account.gps_attrs(self._device)

    @property
    def battery_level(self):
        """Return the battery level of the device."""
        return self._device.battery_level

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
    def source_type(self):
        """Return the source type, eg gps or router, of the device."""
        return SOURCE_TYPE_GPS

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return "mdi:map-marker-outline"
