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

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

ATTR_BATTERY_VOLTAGE = "battery_voltage"
TYPE_BLIND = "blind"
TYPE_GATEWAY = "gateway"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Perform the setup for Motion Blinds."""
    entities = []
    motion_gateway = hass.data[DOMAIN][config_entry.entry_id]

    for blind in motion_gateway.device_list.values():
        await hass.async_add_executor_job(blind.Update)
        entities.append(MotionSignalStrengthSensor(blind, TYPE_BLIND))
        if blind.type == BlindType.TopDownBottomUp:
            entities.append(MotionTDBUBatterySensor(blind, "Bottom"))
            entities.append(MotionTDBUBatterySensor(blind, "Top"))
        elif blind.battery_voltage > 0:
            # Only add battery powered blinds
            entities.append(MotionBatterySensor(blind))

    entities.append(MotionSignalStrengthSensor(motion_gateway, TYPE_GATEWAY))

    async_add_entities(entities)


class MotionBatterySensor(Entity):
    """
    Representation of a Motion Battery Sensor.

    Updates are done by the cover platform.
    """

    def __init__(self, blind):
        """Initialize the Motion Battery Sensor."""
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
        return f"{self._blind.blind_type}-battery-{self._blind.mac}"

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
        attributes = {}
        attributes[ATTR_BATTERY_VOLTAGE] = self._blind.battery_voltage
        return attributes


class MotionTDBUBatterySensor(MotionBatterySensor):
    """
    Representation of a Motion Battery Sensor for a Top Down Bottom Up blind.

    Updates are done by the cover platform.
    """

    def __init__(self, blind, motor):
        """Initialize the Motion Battery Sensor."""
        super().__init__(blind)
        self._motor = motor

    @property
    def unique_id(self):
        """Return the unique id of the blind."""
        return f"{self._blind.mac}-{self._motor}-battery"

    @property
    def name(self):
        """Return the name of the blind battery sensor."""
        return f"{self._blind.blind_type}-{self._motor}-battery-{self._blind.mac}"

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


class MotionSignalStrengthSensor(Entity):
    """Representation of a Motion Signal Strength Sensor."""

    def __init__(self, device, device_type):
        """Initialize the Motion Signal Strength Sensor."""
        self._device = device
        self._device_type = device_type

    def update(self):
        """
        Get the latest status information from gateway.

        Blinds are updated by the cover platform
        """
        if self._device_type == TYPE_GATEWAY:
            self._device.Update()

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
        return f"{self._device.blind_type} signal strength - {self._device.mac}"

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return SIGNAL_STRENGTH_DECIBELS_MILLIWATT

    @property
    def device_class(self):
        """Return the device class of this entity."""
        return DEVICE_CLASS_SIGNAL_STRENGTH

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._device.RSSI
