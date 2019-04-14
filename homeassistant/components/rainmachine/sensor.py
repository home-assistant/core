"""This platform provides support for sensor data from RainMachine."""
import logging

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import (
    DATA_CLIENT, DOMAIN as RAINMACHINE_DOMAIN,
    OPERATION_RESTRICTIONS_UNIVERSAL, SENSOR_UPDATE_TOPIC, SENSORS,
    RainMachineEntity)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up RainMachine sensors based on the old way."""
    pass


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up RainMachine sensors based on a config entry."""
    rainmachine = hass.data[RAINMACHINE_DOMAIN][DATA_CLIENT][entry.entry_id]

    sensors = []
    for sensor_type in rainmachine.sensor_conditions:
        name, icon, unit = SENSORS[sensor_type]
        sensors.append(
            RainMachineSensor(rainmachine, sensor_type, name, icon, unit))

    async_add_entities(sensors, True)


class RainMachineSensor(RainMachineEntity):
    """A sensor implementation for raincloud device."""

    def __init__(self, rainmachine, sensor_type, name, icon, unit):
        """Initialize."""
        super().__init__(rainmachine)

        self._icon = icon
        self._name = name
        self._sensor_type = sensor_type
        self._state = None
        self._unit = unit

    @property
    def icon(self) -> str:
        """Return the icon."""
        return self._icon

    @property
    def should_poll(self):
        """Disable polling."""
        return False

    @property
    def state(self) -> str:
        """Return the name of the entity."""
        return self._state

    @property
    def unique_id(self) -> str:
        """Return a unique, HASS-friendly identifier for this entity."""
        return '{0}_{1}'.format(
            self.rainmachine.device_mac.replace(':', ''), self._sensor_type)

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit

    async def async_added_to_hass(self):
        """Register callbacks."""
        @callback
        def update():
            """Update the state."""
            self.async_schedule_update_ha_state(True)

        self._dispatcher_handlers.append(async_dispatcher_connect(
            self.hass, SENSOR_UPDATE_TOPIC, update))

    async def async_update(self):
        """Update the sensor's state."""
        self._state = self.rainmachine.data[OPERATION_RESTRICTIONS_UNIVERSAL][
            'freezeProtectTemp']
