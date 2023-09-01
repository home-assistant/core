"""Support for Motion Blinds sensors."""
from motionblinds import DEVICE_TYPES_WIFI, BlindType

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, KEY_COORDINATOR, KEY_GATEWAY
from .gateway import device_name
from .entity import MotionCoordinatorEntity

ATTR_BATTERY_VOLTAGE = "battery_voltage"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Perform the setup for Motion Blinds."""
    entities: list[SensorEntity] = []
    motion_gateway = hass.data[DOMAIN][config_entry.entry_id][KEY_GATEWAY]
    coordinator = hass.data[DOMAIN][config_entry.entry_id][KEY_COORDINATOR]

    for blind in motion_gateway.device_list.values():
        entities.append(MotionSignalStrengthSensor(coordinator, blind))
        if blind.type == BlindType.TopDownBottomUp:
            entities.append(MotionTDBUBatterySensor(coordinator, blind, "Bottom"))
            entities.append(MotionTDBUBatterySensor(coordinator, blind, "Top"))
        elif blind.battery_voltage is not None and blind.battery_voltage > 0:
            # Only add battery powered blinds
            entities.append(MotionBatterySensor(coordinator, blind))

    # Do not add signal sensor twice for direct WiFi blinds
    if motion_gateway.device_type not in DEVICE_TYPES_WIFI:
        entities.append(MotionSignalStrengthSensor(coordinator, motion_gateway))

    async_add_entities(entities)


class MotionBatterySensor(MotionCoordinatorEntity, SensorEntity):
    """Representation of a Motion Battery Sensor."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, coordinator, blind):
        """Initialize the Motion Battery Sensor."""
        super().__init__(coordinator, blind)

        self._attr_name = f"{device_name(blind)} battery"
        self._attr_unique_id = f"{blind.mac}-battery"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._blind.battery_level

    @property
    def extra_state_attributes(self):
        """Return device specific state attributes."""
        return {ATTR_BATTERY_VOLTAGE: self._blind.battery_voltage}


class MotionTDBUBatterySensor(MotionBatterySensor):
    """Representation of a Motion Battery Sensor for a Top Down Bottom Up blind."""

    def __init__(self, coordinator, blind, motor):
        """Initialize the Motion Battery Sensor."""
        super().__init__(coordinator, blind)

        self._motor = motor
        self._attr_unique_id = f"{blind.mac}-{motor}-battery"
        self._attr_name = f"{device_name(blind)} {motor} battery"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self._blind.battery_level is None:
            return None
        return self._blind.battery_level[self._motor[0]]

    @property
    def extra_state_attributes(self):
        """Return device specific state attributes."""
        attributes = {}
        if self._blind.battery_voltage is not None:
            attributes[ATTR_BATTERY_VOLTAGE] = self._blind.battery_voltage[
                self._motor[0]
            ]
        return attributes


class MotionSignalStrengthSensor(MotionCoordinatorEntity, SensorEntity):
    """Representation of a Motion Signal Strength Sensor."""

    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_entity_registry_enabled_default = False
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, blind):
        """Initialize the Motion Signal Strength Sensor."""
        super().__init__(coordinator, blind)

        if blind.device_type in DEVICE_TYPES_GATEWAY:
            name = "Motion gateway signal strength"
        else:
            name = f"{device_name(blind)} signal strength"

        self._attr_unique_id = f"{blind.mac}-RSSI"
        self._attr_name = name

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._blind.RSSI
