"""StarLine device tracker."""

from homeassistant.components.device_tracker import SourceType, TrackerEntity
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
    async_add_entities(
        StarlineDeviceTracker(account, device)
        for device in account.api.devices.values()
        if device.support_position
    )


class StarlineDeviceTracker(StarlineEntity, TrackerEntity, RestoreEntity):
    """StarLine device tracker."""

    _attr_translation_key = "location"

    def __init__(self, account: StarlineAccount, device: StarlineDevice) -> None:
        """Set up StarLine entity."""
        super().__init__(account, device, "location")

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
        return self._device.position.get("r", 0)

    @property
    def latitude(self):
        """Return latitude value of the device."""
        return self._device.position["x"]

    @property
    def longitude(self):
        """Return longitude value of the device."""
        return self._device.position["y"]

    @property
    def source_type(self) -> SourceType:
        """Return the source type, eg gps or router, of the device."""
        return SourceType.GPS
