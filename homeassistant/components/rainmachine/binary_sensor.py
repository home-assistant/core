"""This platform provides binary sensors for key RainMachine data."""
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import (
    DATA_CLIENT,
    DOMAIN as RAINMACHINE_DOMAIN,
    PROVISION_SETTINGS,
    RESTRICTIONS_CURRENT,
    RESTRICTIONS_UNIVERSAL,
    SENSOR_UPDATE_TOPIC,
    RainMachineEntity,
)

_LOGGER = logging.getLogger(__name__)

TYPE_FLOW_SENSOR = "flow_sensor"
TYPE_FREEZE = "freeze"
TYPE_FREEZE_PROTECTION = "freeze_protection"
TYPE_HOT_DAYS = "extra_water_on_hot_days"
TYPE_HOURLY = "hourly"
TYPE_MONTH = "month"
TYPE_RAINDELAY = "raindelay"
TYPE_RAINSENSOR = "rainsensor"
TYPE_WEEKDAY = "weekday"

BINARY_SENSORS = {
    TYPE_FLOW_SENSOR: ("Flow Sensor", "mdi:water-pump"),
    TYPE_FREEZE: ("Freeze Restrictions", "mdi:cancel"),
    TYPE_FREEZE_PROTECTION: ("Freeze Protection", "mdi:weather-snowy"),
    TYPE_HOT_DAYS: ("Extra Water on Hot Days", "mdi:thermometer-lines"),
    TYPE_HOURLY: ("Hourly Restrictions", "mdi:cancel"),
    TYPE_MONTH: ("Month Restrictions", "mdi:cancel"),
    TYPE_RAINDELAY: ("Rain Delay Restrictions", "mdi:cancel"),
    TYPE_RAINSENSOR: ("Rain Sensor Restrictions", "mdi:cancel"),
    TYPE_WEEKDAY: ("Weekday Restrictions", "mdi:cancel"),
}


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up RainMachine binary sensors based on a config entry."""
    rainmachine = hass.data[RAINMACHINE_DOMAIN][DATA_CLIENT][entry.entry_id]

    binary_sensors = []
    for sensor_type, (name, icon) in BINARY_SENSORS.items():
        binary_sensors.append(
            RainMachineBinarySensor(rainmachine, sensor_type, name, icon)
        )

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
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return "{0}_{1}".format(
            self.rainmachine.device_mac.replace(":", ""), self._sensor_type
        )

    async def async_added_to_hass(self):
        """Register callbacks."""

        @callback
        def update():
            """Update the state."""
            self.async_schedule_update_ha_state(True)

        self._dispatcher_handlers.append(
            async_dispatcher_connect(self.hass, SENSOR_UPDATE_TOPIC, update)
        )

    async def async_update(self):
        """Update the state."""
        if self._sensor_type == TYPE_FLOW_SENSOR:
            self._state = self.rainmachine.data[PROVISION_SETTINGS]["system"].get(
                "useFlowSensor"
            )
        elif self._sensor_type == TYPE_FREEZE:
            self._state = self.rainmachine.data[RESTRICTIONS_CURRENT]["freeze"]
        elif self._sensor_type == TYPE_FREEZE_PROTECTION:
            self._state = self.rainmachine.data[RESTRICTIONS_UNIVERSAL][
                "freezeProtectEnabled"
            ]
        elif self._sensor_type == TYPE_HOT_DAYS:
            self._state = self.rainmachine.data[RESTRICTIONS_UNIVERSAL][
                "hotDaysExtraWatering"
            ]
        elif self._sensor_type == TYPE_HOURLY:
            self._state = self.rainmachine.data[RESTRICTIONS_CURRENT]["hourly"]
        elif self._sensor_type == TYPE_MONTH:
            self._state = self.rainmachine.data[RESTRICTIONS_CURRENT]["month"]
        elif self._sensor_type == TYPE_RAINDELAY:
            self._state = self.rainmachine.data[RESTRICTIONS_CURRENT]["rainDelay"]
        elif self._sensor_type == TYPE_RAINSENSOR:
            self._state = self.rainmachine.data[RESTRICTIONS_CURRENT]["rainSensor"]
        elif self._sensor_type == TYPE_WEEKDAY:
            self._state = self.rainmachine.data[RESTRICTIONS_CURRENT]["weekDay"]
