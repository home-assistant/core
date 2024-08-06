"""Support for the GPSLogger device tracking."""

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    ATTR_GPS_ACCURACY,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import DOMAIN as GPL_DOMAIN, TRACKER_UPDATE
from .const import (
    ATTR_ACTIVITY,
    ATTR_ALTITUDE,
    ATTR_DIRECTION,
    ATTR_PROVIDER,
    ATTR_SPEED,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Configure a dispatcher connection based on a config entry."""

    @callback
    def _receive_data(device, gps, battery, accuracy, attrs):
        """Receive set location."""
        if device in hass.data[GPL_DOMAIN]["devices"]:
            return

        hass.data[GPL_DOMAIN]["devices"].add(device)

        async_add_entities([GPSLoggerEntity(device, gps, battery, accuracy, attrs)])

    hass.data[GPL_DOMAIN]["unsub_device_tracker"][entry.entry_id] = (
        async_dispatcher_connect(hass, TRACKER_UPDATE, _receive_data)
    )

    # Restore previously loaded devices
    dev_reg = dr.async_get(hass)
    dev_ids = {
        identifier[1]
        for device in dev_reg.devices.get_devices_for_config_entry_id(entry.entry_id)
        for identifier in device.identifiers
    }
    if not dev_ids:
        return

    entities = []
    for dev_id in dev_ids:
        hass.data[GPL_DOMAIN]["devices"].add(dev_id)
        entity = GPSLoggerEntity(dev_id, None, None, None, None)
        entities.append(entity)

    async_add_entities(entities)


class GPSLoggerEntity(TrackerEntity, RestoreEntity):
    """Represent a tracked device."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, device, location, battery, accuracy, attributes):
        """Set up GPSLogger entity."""
        self._accuracy = accuracy
        self._attributes = attributes
        self._name = device
        self._battery = battery
        self._location = location
        self._unsub_dispatcher = None
        self._unique_id = device

    @property
    def battery_level(self):
        """Return battery value of the device."""
        return self._battery

    @property
    def extra_state_attributes(self):
        """Return device specific attributes."""
        return self._attributes

    @property
    def latitude(self):
        """Return latitude value of the device."""
        return self._location[0]

    @property
    def longitude(self):
        """Return longitude value of the device."""
        return self._location[1]

    @property
    def location_accuracy(self):
        """Return the gps accuracy of the device."""
        return self._accuracy

    @property
    def unique_id(self):
        """Return the unique ID."""
        return self._unique_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(GPL_DOMAIN, self._unique_id)},
            name=self._name,
        )

    @property
    def source_type(self) -> SourceType:
        """Return the source type, eg gps or router, of the device."""
        return SourceType.GPS

    async def async_added_to_hass(self) -> None:
        """Register state update callback."""
        await super().async_added_to_hass()
        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass, TRACKER_UPDATE, self._async_receive_data
        )

        # don't restore if we got created with data
        if self._location is not None:
            return

        if (state := await self.async_get_last_state()) is None:
            self._location = (None, None)
            self._accuracy = None
            self._attributes = {
                ATTR_ALTITUDE: None,
                ATTR_ACTIVITY: None,
                ATTR_DIRECTION: None,
                ATTR_PROVIDER: None,
                ATTR_SPEED: None,
            }
            self._battery = None
            return

        attr = state.attributes
        self._location = (attr.get(ATTR_LATITUDE), attr.get(ATTR_LONGITUDE))
        self._accuracy = attr.get(ATTR_GPS_ACCURACY)
        self._attributes = {
            ATTR_ALTITUDE: attr.get(ATTR_ALTITUDE),
            ATTR_ACTIVITY: attr.get(ATTR_ACTIVITY),
            ATTR_DIRECTION: attr.get(ATTR_DIRECTION),
            ATTR_PROVIDER: attr.get(ATTR_PROVIDER),
            ATTR_SPEED: attr.get(ATTR_SPEED),
        }
        self._battery = attr.get(ATTR_BATTERY_LEVEL)

    async def async_will_remove_from_hass(self) -> None:
        """Clean up after entity before removal."""
        await super().async_will_remove_from_hass()
        self._unsub_dispatcher()

    @callback
    def _async_receive_data(self, device, location, battery, accuracy, attributes):
        """Mark the device as seen."""
        if device != self._name:
            return

        self._location = location
        self._battery = battery
        self._accuracy = accuracy
        self._attributes.update(attributes)
        self.async_write_ha_state()
