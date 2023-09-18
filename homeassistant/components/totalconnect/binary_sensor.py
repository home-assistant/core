"""Interfaces with TotalConnect sensors."""
import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

LOW_BATTERY = "low_battery"
TAMPER = "tamper"
POWER = "power"
ZONE = "zone"

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up TotalConnect device sensors based on a config entry."""
    sensors: list = []

    client_locations = hass.data[DOMAIN][entry.entry_id].client.locations

    for location_id, location in client_locations.items():
        sensors.append(TotalConnectAlarmLowBatteryBinarySensor(location))
        sensors.append(TotalConnectAlarmTamperBinarySensor(location))
        sensors.append(TotalConnectAlarmPowerBinarySensor(location))

        for zone in location.zones.values():
            sensors.append(TotalConnectZoneSecurityBinarySensor(location_id, zone))

            if not zone.is_type_button():
                sensors.append(TotalConnectLowBatteryBinarySensor(location_id, zone))
                sensors.append(TotalConnectTamperBinarySensor(location_id, zone))

    async_add_entities(sensors, True)


class TotalConnectZoneBinarySensor(BinarySensorEntity):
    """Represent an TotalConnect zone."""

    def __init__(self, location_id, zone):
        """Initialize the TotalConnect status."""
        self._location_id = location_id
        self._zone = zone
        self._attr_name = f"{zone.description}{self.entity_description.name}"
        self._attr_unique_id = (
            f"{location_id}_{zone.zoneid}_{self.entity_description.key}"
        )
        self._attr_is_on = None
        self._attr_extra_state_attributes = {
            "zone_id": self._zone.zoneid,
            "location_id": self._location_id,
            "partition": self._zone.partition,
        }


class TotalConnectZoneSecurityBinarySensor(TotalConnectZoneBinarySensor):
    """Represent an TotalConnect security zone."""

    entity_description: BinarySensorEntityDescription = BinarySensorEntityDescription(
        key=ZONE, name=""
    )

    @property
    def device_class(self):
        """Return the class of this zone."""
        if self._zone.is_type_fire():
            return BinarySensorDeviceClass.SMOKE
        if self._zone.is_type_carbon_monoxide():
            return BinarySensorDeviceClass.GAS
        if self._zone.is_type_motion():
            return BinarySensorDeviceClass.MOTION
        if self._zone.is_type_medical():
            return BinarySensorDeviceClass.SAFETY
        if self._zone.is_type_temperature():
            return BinarySensorDeviceClass.PROBLEM
        return BinarySensorDeviceClass.DOOR

    def update(self):
        """Return the state of the device."""
        if self._zone.is_faulted() or self._zone.is_triggered():
            self._attr_is_on = True
        else:
            self._attr_is_on = False


class TotalConnectLowBatteryBinarySensor(TotalConnectZoneBinarySensor):
    """Represent an TotalConnect zone low battery status."""

    entity_description: BinarySensorEntityDescription = BinarySensorEntityDescription(
        key=LOW_BATTERY,
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        name=" low battery",
    )

    def update(self):
        """Return the state of the device."""
        self._attr_is_on = self._zone.is_low_battery()


class TotalConnectTamperBinarySensor(TotalConnectZoneBinarySensor):
    """Represent an TotalConnect zone tamper status."""

    entity_description: BinarySensorEntityDescription = BinarySensorEntityDescription(
        key=TAMPER,
        device_class=BinarySensorDeviceClass.TAMPER,
        entity_category=EntityCategory.DIAGNOSTIC,
        name=f" {TAMPER}",
    )

    def update(self):
        """Return the state of the device."""
        self._attr_is_on = self._zone.is_tampered()


class TotalConnectAlarmBinarySensor(BinarySensorEntity):
    """Represent an TotalConnect alarm device binary sensors."""

    def __init__(self, location):
        """Initialize the TotalConnect alarm device binary sensor."""
        self._location = location
        self._attr_name = f"{location.location_name}{self.entity_description.name}"
        self._attr_unique_id = f"{location.location_id}_{self.entity_description.key}"
        self._attr_is_on = None
        self._attr_extra_state_attributes = {
            "location_id": self._location.location_id,
        }


class TotalConnectAlarmLowBatteryBinarySensor(TotalConnectAlarmBinarySensor):
    """Represent an TotalConnect Alarm low battery status."""

    entity_description: BinarySensorEntityDescription = BinarySensorEntityDescription(
        key=LOW_BATTERY,
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        name=" low battery",
    )

    def update(self):
        """Return the state of the device."""
        self._attr_is_on = self._location.is_low_battery()


class TotalConnectAlarmTamperBinarySensor(TotalConnectAlarmBinarySensor):
    """Represent an TotalConnect alarm tamper status."""

    entity_description: BinarySensorEntityDescription = BinarySensorEntityDescription(
        key=TAMPER,
        device_class=BinarySensorDeviceClass.TAMPER,
        entity_category=EntityCategory.DIAGNOSTIC,
        name=f" {TAMPER}",
    )

    def update(self):
        """Return the state of the device."""
        self._attr_is_on = self._location.is_cover_tampered()


class TotalConnectAlarmPowerBinarySensor(TotalConnectAlarmBinarySensor):
    """Represent an TotalConnect alarm power status."""

    entity_description: BinarySensorEntityDescription = BinarySensorEntityDescription(
        key=POWER,
        device_class=BinarySensorDeviceClass.POWER,
        entity_category=EntityCategory.DIAGNOSTIC,
        name=f" {POWER}",
    )

    def update(self):
        """Return the state of the device."""
        self._attr_is_on = not self._location.is_ac_loss()
