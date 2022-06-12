"""Interfaces with TotalConnect sensors."""
import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

LOW_BATTERY = "low battery"
TAMPER = "tamper"
POWER = "power"
ZONE = "zone"

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up TotalConnect device sensors based on a config entry."""
    sensors: Any = []

    client_locations = hass.data[DOMAIN][entry.entry_id].client.locations

    for location_id, location in client_locations.items():

        alarm_battery_description = BinarySensorEntityDescription(
            key=LOW_BATTERY,
            device_class=BinarySensorDeviceClass.BATTERY,
            entity_category=EntityCategory.DIAGNOSTIC,
            name=f"{location.location_name} {LOW_BATTERY}",
        )
        alarm_tamper_description = BinarySensorEntityDescription(
            key=TAMPER,
            device_class=BinarySensorDeviceClass.TAMPER,
            entity_category=EntityCategory.DIAGNOSTIC,
            name=f"{location.location_name} {TAMPER}",
        )
        alarm_power_description = BinarySensorEntityDescription(
            key=POWER,
            device_class=BinarySensorDeviceClass.POWER,
            entity_category=EntityCategory.DIAGNOSTIC,
            name=f"{location.location_name} {POWER}",
        )

        sensors.append(
            TotalConnectAlarmLowBatteryBinarySensor(location, alarm_battery_description)
        )
        sensors.append(
            TotalConnectAlarmTamperBinarySensor(location, alarm_tamper_description)
        )
        sensors.append(
            TotalConnectAlarmPowerBinarySensor(location, alarm_power_description)
        )

        for zone in location.zones.values():

            zone_description = BinarySensorEntityDescription(
                key=ZONE, name=zone.description, device_class=zone_device_class(zone)
            )
            zone_battery_description = BinarySensorEntityDescription(
                key=LOW_BATTERY,
                device_class=BinarySensorDeviceClass.BATTERY,
                entity_category=EntityCategory.DIAGNOSTIC,
                name=f"{zone.description} {LOW_BATTERY}",
            )
            zone_tamper_description = BinarySensorEntityDescription(
                key=TAMPER,
                device_class=BinarySensorDeviceClass.TAMPER,
                entity_category=EntityCategory.DIAGNOSTIC,
                name=f"{zone.description} {TAMPER}",
            )

            sensors.append(
                TotalConnectZoneSecurityBinarySensor(
                    location_id, zone, zone_description
                )
            )

            if not zone.is_type_button():

                sensors.append(
                    TotalConnectLowBatteryBinarySensor(
                        location_id, zone, zone_battery_description
                    )
                )
                sensors.append(
                    TotalConnectTamperBinarySensor(
                        location_id, zone, zone_tamper_description
                    )
                )

    async_add_entities(sensors, True)


def zone_device_class(zone):
    """Return the class of this zone."""
    if zone.is_type_fire():
        return BinarySensorDeviceClass.SMOKE
    if zone.is_type_carbon_monoxide():
        return BinarySensorDeviceClass.GAS
    if zone.is_type_motion():
        return BinarySensorDeviceClass.MOTION
    if zone.is_type_medical():
        return BinarySensorDeviceClass.SAFETY
    # "security" type is a generic category so test for it last
    if zone.is_type_security():
        return BinarySensorDeviceClass.DOOR

    _LOGGER.error(
        "TotalConnect zone %s reported an unexpected device class", zone.zoneid
    )
    return None


class TotalConnectZoneBinarySensor(BinarySensorEntity):
    """Represent an TotalConnect zone."""

    def __init__(self, location_id, zone, description):
        """Initialize the TotalConnect status."""
        self._location_id = location_id
        self._zone = zone
        self.entity_description = description
        self._attr_unique_id = f"{location_id} {zone.zoneid} {description.key}"
        self._attr_is_on = None

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attributes = {
            "zone_id": self._zone.zoneid,
            "location_id": self._location_id,
            "partition": self._zone.partition,
        }
        return attributes


class TotalConnectZoneSecurityBinarySensor(TotalConnectZoneBinarySensor):
    """Represent an TotalConnect security zone."""

    def update(self):
    def update(self) -> None:
        """Return the state of the device."""
        if self._zone.is_faulted() or self._zone.is_triggered():
            self._attr_is_on = True
        else:
            self._attr_is_on = False


class TotalConnectLowBatteryBinarySensor(TotalConnectZoneBinarySensor):
    """Represent an TotalConnect zone low battery status."""

    def update(self):
        """Return the state of the device."""
        self._attr_is_on = self._zone.is_low_battery()


class TotalConnectTamperBinarySensor(TotalConnectZoneBinarySensor):
    """Represent an TotalConnect zone tamper status."""

    def update(self):
        """Return the state of the device."""
        self._attr_is_on = self._zone.is_tampered()


class TotalConnectAlarmBinarySensor(BinarySensorEntity):
    """Represent an TotalConnect alarm device binary sensors."""

    def __init__(self, location, description):
        """Initialize the TotalConnect alarm device binary sensor."""
        self._location = location
        self.entity_description = description
        self._attr_unique_id = f"{location.location_id} {description.key}"
        self._attr_is_on = None

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attributes = {
            "location_id": self._location.location_id,
        }
        return attributes


class TotalConnectAlarmLowBatteryBinarySensor(TotalConnectAlarmBinarySensor):
    """Represent an TotalConnect Alarm low battery status."""

    def update(self):
        """Return the state of the device."""
        self._attr_is_on = self._location.is_low_battery()


class TotalConnectAlarmTamperBinarySensor(TotalConnectAlarmBinarySensor):
    """Represent an TotalConnect alarm tamper status."""

    def update(self):
        """Return the state of the device."""
        self._attr_is_on = self._location.is_cover_tampered()


class TotalConnectAlarmPowerBinarySensor(TotalConnectAlarmBinarySensor):
    """Represent an TotalConnect alarm power status."""

    def update(self):
        """Return the state of the device."""
        self._attr_is_on = not self._location.is_ac_loss()
