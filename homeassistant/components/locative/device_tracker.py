"""Support for the Locative platform."""
from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN as LT_DOMAIN, TRACKER_UPDATE


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Configure a dispatcher connection based on a config entry."""

    @callback
    def _receive_data(device, location, location_name):
        """Receive set location."""
        if device in hass.data[LT_DOMAIN]["devices"]:
            return

        hass.data[LT_DOMAIN]["devices"].add(device)

        async_add_entities([LocativeEntity(device, location, location_name)])

    hass.data[LT_DOMAIN]["unsub_device_tracker"][
        entry.entry_id
    ] = async_dispatcher_connect(hass, TRACKER_UPDATE, _receive_data)


class LocativeEntity(TrackerEntity):
    """Represent a tracked device."""

    def __init__(self, device, location, location_name):
        """Set up Locative entity."""
        self._name = device
        self._location = location
        self._location_name = location_name
        self._unsub_dispatcher = None

    @property
    def latitude(self):
        """Return latitude value of the device."""
        return self._location[0]

    @property
    def longitude(self):
        """Return longitude value of the device."""
        return self._location[1]

    @property
    def location_name(self):
        """Return a location name for the current location of the device."""
        return self._location_name

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def source_type(self) -> SourceType:
        """Return the source type, eg gps or router, of the device."""
        return SourceType.GPS

    async def async_added_to_hass(self) -> None:
        """Register state update callback."""
        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass, TRACKER_UPDATE, self._async_receive_data
        )

    async def async_will_remove_from_hass(self) -> None:
        """Clean up after entity before removal."""
        self._unsub_dispatcher()

    @callback
    def _async_receive_data(self, device, location, location_name):
        """Update device data."""
        if device != self._name:
            return
        self._location_name = location_name
        self._location = location
        self.async_write_ha_state()
