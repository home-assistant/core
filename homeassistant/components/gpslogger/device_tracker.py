"""Support for the GPSLogger device tracking."""

from homeassistant.components.device_tracker import TrackerEntity
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
        self._attr_location_accuracy = accuracy
        self._attr_extra_state_attributes = attributes
        self._name = device
        self._battery = battery
        if location:
            self._attr_latitude = location[0]
            self._attr_longitude = location[1]
        self._unsub_dispatcher = None
        self._attr_unique_id = device
        self._attr_device_info = DeviceInfo(
            identifiers={(GPL_DOMAIN, device)},
            name=device,
        )

    @property
    def battery_level(self):
        """Return battery value of the device."""
        return self._battery

    async def async_added_to_hass(self) -> None:
        """Register state update callback."""
        await super().async_added_to_hass()
        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass, TRACKER_UPDATE, self._async_receive_data
        )

        # don't restore if we got created with data
        if self.latitude is not None:
            return

        if (state := await self.async_get_last_state()) is None:
            self._attr_latitude = None
            self._attr_longitude = None
            self._attr_location_accuracy = 0
            self._attr_extra_state_attributes = {
                ATTR_ALTITUDE: None,
                ATTR_ACTIVITY: None,
                ATTR_DIRECTION: None,
                ATTR_PROVIDER: None,
                ATTR_SPEED: None,
            }
            self._battery = None
            return

        attr = state.attributes
        self._attr_latitude = attr.get(ATTR_LATITUDE)
        self._attr_longitude = attr.get(ATTR_LONGITUDE)
        self._attr_location_accuracy = attr.get(ATTR_GPS_ACCURACY, 0)
        self._attr_extra_state_attributes = {
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

        self._attr_latitude = location[0]
        self._attr_longitude = location[1]
        self._battery = battery
        self._attr_location_accuracy = accuracy
        self._attr_extra_state_attributes.update(attributes)
        self.async_write_ha_state()
