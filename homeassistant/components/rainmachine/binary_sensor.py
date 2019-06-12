"""This platform provides binary sensors for key RainMachine data."""
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import (
    BINARY_SENSORS, DATA_CLIENT, DOMAIN as RAINMACHINE_DOMAIN,
    PROVISION_SETTINGS, RESTRICTIONS_CURRENT, RESTRICTIONS_UNIVERSAL,
    SENSOR_UPDATE_TOPIC, TYPE_FLOW_SENSOR, TYPE_FREEZE, TYPE_FREEZE_PROTECTION,
    TYPE_HOT_DAYS, TYPE_HOURLY, TYPE_MONTH, TYPE_RAINDELAY, TYPE_RAINSENSOR,
    TYPE_WEEKDAY, RainMachineEntity)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up  RainMachine binary sensors based on the old way."""
    pass


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up RainMachine binary sensors based on a config entry."""
    rainmachine = hass.data[RAINMACHINE_DOMAIN][DATA_CLIENT][entry.entry_id]

    binary_sensors = []
    for sensor_type in rainmachine.binary_sensor_conditions:
        name, icon = BINARY_SENSORS[sensor_type]
        binary_sensors.append(
            RainMachineBinarySensor(rainmachine, sensor_type, name, icon))

    async_add_entities(binary_sensors, True)


class RainMachineBinarySensor(RainMachineEntity, BinarySensorDevice):
    """A sensor implementation for raincloud device."""

    def __init__(self, rainmachine, sensor_type, name, icon):
        """Initialize the sensor."""
        super().__init__(rainmachine)

        self._icon = icon
        self._name = name
        self._sensor_type = sensor_type
        self._state = None

    @property
    def icon(self) -> str:
        """Return the icon."""
        return self._icon

    @property
    def is_on(self):
        """Return the status of the sensor."""
        return self._state

    @property
    def should_poll(self):
        """Disable polling."""
        return False

    @property
    def unique_id(self) -> str:
        """Return a unique, HASS-friendly identifier for this entity."""
        return '{0}_{1}'.format(
            self.rainmachine.device_mac.replace(':', ''), self._sensor_type)

    async def async_added_to_hass(self):
        """Register callbacks."""
        @callback
        def update():
            """Update the state."""
            self.async_schedule_update_ha_state(True)

        self._dispatcher_handlers.append(async_dispatcher_connect(
            self.hass, SENSOR_UPDATE_TOPIC, update))

    async def async_update(self):
        """Update the state."""
        if self._sensor_type == TYPE_FLOW_SENSOR:
            self._state = self.rainmachine.data[PROVISION_SETTINGS].get(
                'useFlowSensor')
        elif self._sensor_type == TYPE_FREEZE:
            self._state = self.rainmachine.data[RESTRICTIONS_CURRENT]['freeze']
        elif self._sensor_type == TYPE_FREEZE_PROTECTION:
            self._state = self.rainmachine.data[RESTRICTIONS_UNIVERSAL][
                'freezeProtectEnabled']
        elif self._sensor_type == TYPE_HOT_DAYS:
            self._state = self.rainmachine.data[RESTRICTIONS_UNIVERSAL][
                'hotDaysExtraWatering']
        elif self._sensor_type == TYPE_HOURLY:
            self._state = self.rainmachine.data[RESTRICTIONS_CURRENT]['hourly']
        elif self._sensor_type == TYPE_MONTH:
            self._state = self.rainmachine.data[RESTRICTIONS_CURRENT]['month']
        elif self._sensor_type == TYPE_RAINDELAY:
            self._state = self.rainmachine.data[RESTRICTIONS_CURRENT][
                'rainDelay']
        elif self._sensor_type == TYPE_RAINSENSOR:
            self._state = self.rainmachine.data[RESTRICTIONS_CURRENT][
                'rainSensor']
        elif self._sensor_type == TYPE_WEEKDAY:
            self._state = self.rainmachine.data[RESTRICTIONS_CURRENT][
                'weekDay']
