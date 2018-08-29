"""
Support for Salda Smarty XP/XV Ventilation Unit Sensors.

For more details about this component, please refer to the documentation at:
https://home-assistant.io/components/sensor.smarty/
"""
import logging

from homeassistant.core import callback
from homeassistant.components.smarty import (
    DATA_SMARTY, Smarty, SIGNAL_UPDATE_SMARTY)
from homeassistant.const import (
    TEMP_CELSIUS, DEVICE_CLASS_TEMPERATURE,
    STATE_UNKNOWN)
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

DEPENDENCIES = ['smarty']

_LOGGER = logging.getLogger(__name__)

DEVICE_CLASS_RPM = 'rpm'
RPM = 'rpm'


async def async_setup_platform(hass, config, async_add_devices,
                               discovery_info=None):
    """Set up the Smarty Sensor Platform."""
    smarty = hass.data[DATA_SMARTY]

    sensors = [SmartySensor(smarty.name + " Supply Air",
                            'IR_SUPPLY_AIR_TEMPERATURE',
                            DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS,
                            smarty),
               SmartySensor(smarty.name + " Extract Air",
                            'IR_EXTRACT_AIR_TEMPERATURE',
                            DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS,
                            smarty),
               SmartySensor(smarty.name + ' Outdoor Air',
                            'IR_OUTDOOR_AIR_TEMPERATURE',
                            DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS,
                            smarty),
               SmartySensor(smarty.name + ' Supply Fan Speed',
                            'IR_SUPPLY_FAN_SPEED_RPM',
                            DEVICE_CLASS_RPM, RPM,
                            smarty),
               SmartySensor(smarty.name + ' Extract Fan Speed',
                            'IR_EXTRACT_FAN_SPEED_RPM',
                            DEVICE_CLASS_RPM, RPM,
                            smarty)]

    async_add_devices(sensors)


class SmartySensor(Entity):
    """Representation of a Smarty Sensor."""

    def __init__(self, name: str, sensor_type: str, device_class: str,
                 unit_of_measurement: str, smarty: Smarty):
        """Initialize the entity."""
        self._name = name
        self._sensor_type = sensor_type
        self._state = STATE_UNKNOWN
        self._device_class = device_class
        self._unit_of_measurement = unit_of_measurement
        self._smarty = smarty

    @property
    def should_poll(self) -> bool:
        """Do not poll."""
        return False

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return self._device_class

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement

    async def async_added_to_hass(self):
        """Call to update fan."""
        async_dispatcher_connect(self.hass,
                                 SIGNAL_UPDATE_SMARTY,
                                 self._update_callback)

    @callback
    def _update_callback(self):
        """Call update method."""
        self.async_schedule_update_ha_state(True)

    def update(self) -> None:
        """Update state."""
        _LOGGER.debug('Updating sensor %s', self._sensor_type)
        self._state = self._smarty.get_sensor(self._sensor_type)
