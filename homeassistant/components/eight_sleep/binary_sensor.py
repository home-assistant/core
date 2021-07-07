"""Support for Eight Sleep binary sensors."""
import logging

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_OCCUPANCY,
    BinarySensorEntity,
)
from homeassistant.core import callback

from . import (
    CONF_BINARY_SENSORS,
    DATA_API,
    DATA_EIGHT,
    DATA_HEAT,
    NAME_MAP,
    EightSleepEntity,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the eight sleep binary sensor."""
    if discovery_info is None:
        return

    name = "Eight"
    sensors = discovery_info[CONF_BINARY_SENSORS]
    eight = hass.data[DATA_EIGHT][DATA_API]
    heat_coordinator = hass.data[DATA_EIGHT][DATA_HEAT]

    all_sensors = []

    for sensor in sensors:
        all_sensors.append(EightHeatSensor(name, heat_coordinator, eight, sensor))

    async_add_entities(all_sensors, True)


class EightHeatSensor(EightSleepEntity, BinarySensorEntity):
    """Representation of a Eight Sleep heat-based sensor."""

    def __init__(self, name, coordinator, eight, sensor):
        """Initialize the sensor."""
        super().__init__(coordinator, eight)

        self._sensor = sensor
        self._mapped_name = NAME_MAP.get(self._sensor, self._sensor)
        self._state = None

        self._side = self._sensor.split("_")[0]
        self._userid = self._eight.fetch_userid(self._side)
        self._usrobj = self._eight.users[self._userid]

        self._attr_name = f"{name} {self._mapped_name}"
        self._attr_device_class = DEVICE_CLASS_OCCUPANCY

        _LOGGER.debug(
            "Presence Sensor: %s, Side: %s, User: %s",
            self._sensor,
            self._side,
            self._userid,
        )

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._state

    @callback
    def _handle_coordinator_update(self):
        """Handle updated data from the coordinator."""
        self._state = self._usrobj.bed_presence
        super()._handle_coordinator_update()
