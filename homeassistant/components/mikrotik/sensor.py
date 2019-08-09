"""Mikrotik status sensors."""
import logging

from homeassistant.helpers.entity import Entity
from homeassistant.const import CONF_HOST
from homeassistant.util import slugify
from .const import DOMAIN, HOSTS, CONF_WAN_PORT, SENSORS, MEGA, UNITS

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the mikrotik sensors."""
    if discovery_info is None:
        return

    host = discovery_info[CONF_HOST]
    api = hass.data[DOMAIN][HOSTS][host]["api"]
    hostname = api.get_hostname()
    add_entities(
        [
            MikrotikSensor(api, hostname, sensor_type, discovery_info)
            for sensor_type in discovery_info["sensors"]
        ]
    )


class MikrotikSensor(Entity):
    """Representation of a mikrotik sensor."""

    def __init__(self, api, hostname, sensor_type, config):
        """Initialize the sensor."""
        self.api = api
        self.config = config
        self.sensor_type = sensor_type
        self.sensor_data = SENSORS[sensor_type]
        self._available = True
        self._state = None
        self._attrs = {}
        self._name = "{} {}".format(hostname, SENSORS[sensor_type][0])
        self._unit = self.sensor_data[1]
        self._icon = self.sensor_data[2]
        self._state_item = self.sensor_data[3]
        self._attr_items = self.sensor_data[5]
        self._cmds = self.sensor_data[4]
        self._params = self.sensor_data[6]
        if self._params is not None and "interface" in self._params:
            self._params["interface"] = self.config.get(CONF_WAN_PORT)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def available(self):
        """Return the availability state."""
        return self._available

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attrs

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    def update(self):
        """Get the latest data and updates the state."""
        results = {}
        self._attrs = {}
        self._state = None
        self._available = self.api.connected()
        if not self._available:
            return

        for cmd in self._cmds:
            data = self.api.command(cmd, self._params)
            if data is None:
                _LOGGER.error("Mikrotik missing sensor data %s", self._name)
                self._available = False
                return
            results.update(data[0])

        for key in results:
            add_unit = False
            value = results.get(key)
            if any(unit in key for unit in UNITS):
                add_unit = True
                try:
                    value = "%.1f" % (float(value) / MEGA)
                except Exception as error:
                    _LOGGER.error(
                        "Mikrotik %s error %s", self._name, error
                    )
                    pass

            if key == self._state_item:
                self._state = value
            elif key in self._attr_items:
                if add_unit:
                    value = "{} {}".format(value, self._unit)
                self._attrs[slugify(key)] = value
