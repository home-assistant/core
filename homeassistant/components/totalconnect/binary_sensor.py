"""Interfaces with TotalConnect sensors."""
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up TotalConnect device sensors based on a config entry."""
    sensors = []

    client_locations = hass.data[DOMAIN][entry.entry_id].client.locations

    for location_id, location in client_locations.items():
        for zone_id, zone in location.zones.items():
            sensors.append(TotalConnectBinarySensor(zone_id, location_id, zone))

    async_add_entities(sensors, True)


class TotalConnectBinarySensor(BinarySensorEntity):
    """Represent an TotalConnect zone."""

    def __init__(self, zone_id, location_id, zone):
        """Initialize the TotalConnect status."""
        self._zone_id = zone_id
        self._location_id = location_id
        self._zone = zone
        self._name = self._zone.description
        self._unique_id = f"{location_id} {zone_id}"
        self._is_on = None
        self._is_tampered = None
        self._is_low_battery = None

    @property
    def unique_id(self):
        """Return the unique id."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    def update(self):
        """Return the state of the device."""
        self._is_tampered = self._zone.is_tampered()
        self._is_low_battery = self._zone.is_low_battery()

        if self._zone.is_faulted() or self._zone.is_triggered():
            self._is_on = True
        else:
            self._is_on = False

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._is_on

    @property
    def device_class(self):
        """Return the class of this device, from BinarySensorDeviceClass."""
        if self._zone.is_type_security():
            return BinarySensorDeviceClass.DOOR
        if self._zone.is_type_fire():
            return BinarySensorDeviceClass.SMOKE
        if self._zone.is_type_carbon_monoxide():
            return BinarySensorDeviceClass.GAS
        if self._zone.is_type_motion():
            return BinarySensorDeviceClass.MOTION
        if self._zone.is_type_medical():
            return BinarySensorDeviceClass.SAFETY
        return None

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attributes = {
            "zone_id": self._zone_id,
            "location_id": self._location_id,
            "low_battery": self._is_low_battery,
            "tampered": self._is_tampered,
            "partition": self._zone.partition,
        }
        return attributes
