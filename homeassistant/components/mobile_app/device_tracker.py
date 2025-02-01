"""Device tracker for Mobile app."""

from homeassistant.components.device_tracker import (
    ATTR_BATTERY,
    ATTR_GPS,
    ATTR_GPS_ACCURACY,
    ATTR_LOCATION_NAME,
    TrackerEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    ATTR_DEVICE_ID,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    ATTR_ALTITUDE,
    ATTR_COURSE,
    ATTR_DEVICE_NAME,
    ATTR_SPEED,
    ATTR_VERTICAL_ACCURACY,
    SIGNAL_LOCATION_UPDATE,
)
from .helpers import device_info

ATTR_KEYS = (ATTR_ALTITUDE, ATTR_COURSE, ATTR_SPEED, ATTR_VERTICAL_ACCURACY)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Mobile app based off an entry."""
    entity = MobileAppEntity(entry)
    async_add_entities([entity])


class MobileAppEntity(TrackerEntity, RestoreEntity):
    """Represent a tracked device."""

    def __init__(self, entry, data=None):
        """Set up Mobile app entity."""
        self._entry = entry
        self._data = data
        self._dispatch_unsub = None

    @property
    def unique_id(self):
        """Return the unique ID."""
        return self._entry.data[ATTR_DEVICE_ID]

    @property
    def battery_level(self):
        """Return the battery level of the device."""
        return self._data.get(ATTR_BATTERY)

    @property
    def extra_state_attributes(self):
        """Return device specific attributes."""
        attrs = {}
        for key in ATTR_KEYS:
            if (value := self._data.get(key)) is not None:
                attrs[key] = value

        return attrs

    @property
    def location_accuracy(self):
        """Return the gps accuracy of the device."""
        return self._data.get(ATTR_GPS_ACCURACY)

    @property
    def latitude(self):
        """Return latitude value of the device."""
        if (gps := self._data.get(ATTR_GPS)) is None:
            return None

        return gps[0]

    @property
    def longitude(self):
        """Return longitude value of the device."""
        if (gps := self._data.get(ATTR_GPS)) is None:
            return None

        return gps[1]

    @property
    def location_name(self):
        """Return a location name for the current location of the device."""
        if location_name := self._data.get(ATTR_LOCATION_NAME):
            return location_name
        return None

    @property
    def name(self):
        """Return the name of the device."""
        return self._entry.data[ATTR_DEVICE_NAME]

    @property
    def device_info(self):
        """Return the device info."""
        return device_info(self._entry.data)

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to Home Assistant."""
        await super().async_added_to_hass()
        self._dispatch_unsub = async_dispatcher_connect(
            self.hass,
            SIGNAL_LOCATION_UPDATE.format(self._entry.entry_id),
            self.update_data,
        )

        # Don't restore if we got set up with data.
        if self._data is not None:
            return

        if (state := await self.async_get_last_state()) is None:
            self._data = {}
            return

        attr = state.attributes
        data = {
            ATTR_GPS: (attr.get(ATTR_LATITUDE), attr.get(ATTR_LONGITUDE)),
            ATTR_GPS_ACCURACY: attr.get(ATTR_GPS_ACCURACY),
            ATTR_BATTERY: attr.get(ATTR_BATTERY_LEVEL),
        }
        data.update({key: attr[key] for key in attr if key in ATTR_KEYS})
        self._data = data

    async def async_will_remove_from_hass(self) -> None:
        """Call when entity is being removed from hass."""
        await super().async_will_remove_from_hass()

        if self._dispatch_unsub:
            self._dispatch_unsub()
            self._dispatch_unsub = None

    @callback
    def update_data(self, data):
        """Mark the device as seen."""
        self._data = data
        self.async_write_ha_state()
