"""Interfaces with TotalConnect sensors."""
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up TotalConnect device sensors based on a config entry."""
    sensors: Any = []

    client_locations = hass.data[DOMAIN][entry.entry_id].client.locations

    for location_id, location in client_locations.items():

        sensors.append(TotalConnectAlarmLowBatteryBinarySensor(location))
        sensors.append(TotalConnectAlarmTamperBinarySensor(location))
        sensors.append(TotalConnectAlarmPowerBinarySensor(location))

        for zone_id, zone in location.zones.items():
            sensors.append(TotalConnectZoneBinarySensor(zone_id, location_id, zone))

            if not zone.is_type_button():
                sensors.append(
                    TotalConnectLowBatteryBinarySensor(zone_id, location_id, zone)
                )
                sensors.append(
                    TotalConnectTamperBinarySensor(zone_id, location_id, zone)
                )

    async_add_entities(sensors, True)


class TotalConnectLowBatteryDescription(BinarySensorEntityDescription):
    """EntityDescription for low battery."""

    device_class = BinarySensorDeviceClass.BATTERY
    entity_category = EntityCategory.DIAGNOSTIC


class TotalConnectTamperDescription(BinarySensorEntityDescription):
    """EntityDescription for tamper."""

    device_class = BinarySensorDeviceClass.TAMPER
    entity_category = EntityCategory.DIAGNOSTIC


class TotalConnectPowerDescription(BinarySensorEntityDescription):
    """EntityDescription for power sensor."""

    device_class = BinarySensorDeviceClass.POWER
    entity_category = EntityCategory.DIAGNOSTIC


class TotalConnectBinarySensor(BinarySensorEntity):
    """Represent an TotalConnect zone."""

    _unique_id = None
    _name = None
    _zone = None
    _zone_id = None
    _location_id = None
    _is_on = None

    @property
    def unique_id(self):
        """Return the unique id."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._is_on

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attributes = {
            "zone_id": self._zone_id,
            "location_id": self._location_id,
            "partition": self._zone.partition,
        }
        return attributes


class TotalConnectZoneBinarySensor(TotalConnectBinarySensor):
    """Represent an TotalConnect zone."""

    def __init__(self, zone_id, location_id, zone):
        """Initialize the TotalConnect status."""
        self._zone_id = zone_id
        self._location_id = location_id
        self._zone = zone
        self._name = self._zone.description
        self._unique_id = f"{location_id} {zone_id}"
        self._is_on = None

    def update(self):
    def update(self) -> None:
        """Return the state of the device."""
        if self._zone.is_faulted() or self._zone.is_triggered():
            self._is_on = True
        else:
            self._is_on = False

    @property
    def device_class(self):
        """Return the class of this device, from BinarySensorDeviceClass."""
        if self._zone.is_type_fire():
            return BinarySensorDeviceClass.SMOKE
        if self._zone.is_type_carbon_monoxide():
            return BinarySensorDeviceClass.GAS
        if self._zone.is_type_motion():
            return BinarySensorDeviceClass.MOTION
        if self._zone.is_type_medical():
            return BinarySensorDeviceClass.SAFETY
        # "security" type is a generic category so test for it last
        if self._zone.is_type_security():
            return BinarySensorDeviceClass.DOOR

        raise HomeAssistantError(
            f"TotalConnect zone {self._zone_id} reported an unexpected device class."
        )


class TotalConnectLowBatteryBinarySensor(TotalConnectBinarySensor):
    """Represent an TotalConnect zone low battery status."""

    def __init__(self, zone_id, location_id, zone):
        """Initialize the TotalConnect status."""
        self._zone_id = zone_id
        self._location_id = location_id
        self._zone = zone
        self._name = f"{self._zone.description} low battery"
        self._unique_id = f"{location_id} {zone_id} low battery"
        self._is_on = None
        self.entity_description = TotalConnectLowBatteryDescription

    def update(self):
        """Return the state of the device."""
        self._is_on = self._zone.is_low_battery()


class TotalConnectTamperBinarySensor(TotalConnectBinarySensor):
    """Represent an TotalConnect zone tamper status."""

    def __init__(self, zone_id, location_id, zone):
        """Initialize the TotalConnect status."""
        self._zone_id = zone_id
        self._location_id = location_id
        self._zone = zone
        self._name = f"{self._zone.description} tamper"
        self._unique_id = f"{location_id} {zone_id} tamper"
        self._is_on = None
        self.entity_description = TotalConnectTamperDescription

    def update(self):
        """Return the state of the device."""
        self._is_on = self._zone.is_tampered()


class TotalConnectAlarmBinarySensor(BinarySensorEntity):
    """Represent an TotalConnect alarm device binary sensors."""

    _unique_id = None
    _name = None
    _location_id = None
    _is_on = None

    @property
    def unique_id(self):
        """Return the unique id."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._is_on

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attributes = {
            "location_id": self._location_id,
        }
        return attributes


class TotalConnectAlarmLowBatteryBinarySensor(TotalConnectAlarmBinarySensor):
    """Represent an TotalConnect Alarm low battery status."""

    def __init__(self, location):
        """Initialize the TotalConnect alarm low battery sensor."""
        self._location = location
        self._location_id = location.location_id
        self._name = f"{location.location_name} low battery"
        self._unique_id = f"{location.location_id} low battery"
        self._is_on = None
        self.entity_description = TotalConnectLowBatteryDescription

    def update(self):
        """Return the state of the device."""
        self._is_on = self._location.is_low_battery()


class TotalConnectAlarmTamperBinarySensor(TotalConnectAlarmBinarySensor):
    """Represent an TotalConnect alarm tamper status."""

    def __init__(self, location):
        """Initialize the TotalConnect alarm tamper sensor."""
        self._location = location
        self._location_id = location.location_id
        self._name = f"{location.location_name} tamper"
        self._unique_id = f"{location.location_id} tamper"
        self._is_on = None
        self.entity_description = TotalConnectTamperDescription

    def update(self):
        """Return the state of the device."""
        self._is_on = self._location.is_cover_tampered()


class TotalConnectAlarmPowerBinarySensor(TotalConnectAlarmBinarySensor):
    """Represent an TotalConnect alarm power status."""

    def __init__(self, location):
        """Initialize the TotalConnect alarm power sensor."""
        self._location = location
        self._location_id = location.location_id
        self._name = f"{location.location_name} power"
        self._unique_id = f"{location.location_id} power"
        self._is_on = None
        self.entity_description = TotalConnectPowerDescription

    def update(self):
        """Return the state of the device."""
        self._is_on = not self._location.is_ac_loss()
