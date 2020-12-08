"""Support for Motion Blinds sensors."""
import logging

from motionblinds import BlindType

from homeassistant.const import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_SIGNAL_STRENGTH,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, KEY_COORDINATOR, KEY_GATEWAY

_LOGGER = logging.getLogger(__name__)

ATTR_BATTERY_VOLTAGE = "battery_voltage"
TYPE_BLIND = "blind"
TYPE_GATEWAY = "gateway"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Perform the setup for Motion Blinds."""
    entities = []
    motion_gateway = hass.data[DOMAIN][config_entry.entry_id][KEY_GATEWAY]
    coordinator = hass.data[DOMAIN][config_entry.entry_id][KEY_COORDINATOR]

    for blind in motion_gateway.device_list.values():
        entities.append(MotionSignalStrengthSensor(coordinator, blind, TYPE_BLIND))
        if blind.type == BlindType.TopDownBottomUp:
            entities.append(MotionTDBUBatterySensor(coordinator, blind, "Bottom"))
            entities.append(MotionTDBUBatterySensor(coordinator, blind, "Top"))
        elif blind.battery_voltage > 0:
            # Only add battery powered blinds
            entities.append(MotionBatterySensor(coordinator, blind))

    entities.append(
        MotionSignalStrengthSensor(coordinator, motion_gateway, TYPE_GATEWAY)
    )

    async_add_entities(entities)


class MotionBatterySensor(CoordinatorEntity, Entity):
    """
    Representation of a Motion Battery Sensor.

    Updates are done by the cover platform.
    """

    def __init__(self, coordinator, blind):
        """Initialize the Motion Battery Sensor."""
        super().__init__(coordinator)

        self._blind = blind

    @property
    def unique_id(self):
        """Return the unique id of the blind."""
        return f"{self._blind.mac}-battery"

    @property
    def device_info(self):
        """Return the device info of the blind."""
        return {"identifiers": {(DOMAIN, self._blind.mac)}}

    @property
    def name(self):
        """Return the name of the blind battery sensor."""
        return f"{self._blind.blind_type}-battery-{self._blind.mac[12:]}"

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return PERCENTAGE

    @property
    def device_class(self):
        """Return the device class of this entity."""
        return DEVICE_CLASS_BATTERY

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._blind.battery_level

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        return {ATTR_BATTERY_VOLTAGE: self._blind.battery_voltage}


class MotionTDBUBatterySensor(MotionBatterySensor):
    """
    Representation of a Motion Battery Sensor for a Top Down Bottom Up blind.

    Updates are done by the cover platform.
    """

    def __init__(self, coordinator, blind, motor):
        """Initialize the Motion Battery Sensor."""
        super().__init__(coordinator, blind)

        self._motor = motor

    @property
    def unique_id(self):
        """Return the unique id of the blind."""
        return f"{self._blind.mac}-{self._motor}-battery"

    @property
    def name(self):
        """Return the name of the blind battery sensor."""
        return f"{self._blind.blind_type}-{self._motor}-battery-{self._blind.mac[12:]}"

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._blind.battery_level is None:
            return None
        return self._blind.battery_level[self._motor[0]]

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        attributes = {}
        if self._blind.battery_voltage is not None:
            attributes[ATTR_BATTERY_VOLTAGE] = self._blind.battery_voltage[
                self._motor[0]
            ]
        return attributes


class MotionSignalStrengthSensor(CoordinatorEntity, Entity):
    """Representation of a Motion Signal Strength Sensor."""

    def __init__(self, coordinator, device, device_type):
        """Initialize the Motion Signal Strength Sensor."""
        super().__init__(coordinator)

        self._device = device
        self._device_type = device_type

    @property
    def unique_id(self):
        """Return the unique id of the blind."""
        return f"{self._device.mac}-RSSI"

    @property
    def device_info(self):
        """Return the device info of the blind."""
        return {"identifiers": {(DOMAIN, self._device.mac)}}

    @property
    def name(self):
        """Return the name of the blind signal strength sensor."""
        if self._device_type == TYPE_GATEWAY:
            return "Motion gateway signal strength"
        return f"{self._device.blind_type} signal strength - {self._device.mac[12:]}"

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return SIGNAL_STRENGTH_DECIBELS_MILLIWATT

    @property
    def device_class(self):
        """Return the device class of this entity."""
        return DEVICE_CLASS_SIGNAL_STRENGTH

    @property
    def entity_registry_enabled_default(self):
        """Return if the entity should be enabled when first added to the entity registry."""
        return False

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._device.RSSI
