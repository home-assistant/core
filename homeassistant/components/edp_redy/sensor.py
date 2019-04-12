"""Support for EDP re:dy sensors."""
import logging

from homeassistant.const import POWER_WATT
from homeassistant.helpers.entity import Entity

from . import EDP_REDY, EdpRedyDevice

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['edp_redy']

# Load power in watts (W)
ATTR_ACTIVE_POWER = 'active_power'


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Perform the setup for re:dy devices."""
    from edp_redy.session import ACTIVE_POWER_ID

    session = hass.data[EDP_REDY]
    devices = []

    # Create sensors for modules
    for device_json in session.modules_dict.values():
        if 'HA_POWER_METER' not in device_json['Capabilities']:
            continue
        devices.append(EdpRedyModuleSensor(session, device_json))

    # Create a sensor for global active power
    devices.append(EdpRedySensor(session, ACTIVE_POWER_ID, "Power Home",
                                 'mdi:flash', POWER_WATT))

    async_add_entities(devices, True)


class EdpRedySensor(EdpRedyDevice, Entity):
    """Representation of a EDP re:dy generic sensor."""

    def __init__(self, session, sensor_id, name, icon, unit):
        """Initialize the sensor."""
        super().__init__(session, sensor_id, name)

        self._icon = icon
        self._unit = unit

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return self._icon

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this sensor."""
        return self._unit

    async def async_update(self):
        """Parse the data for this sensor."""
        if self._id in self._session.values_dict:
            self._state = self._session.values_dict[self._id]
            self._is_available = True
        else:
            self._is_available = False


class EdpRedyModuleSensor(EdpRedyDevice, Entity):
    """Representation of a EDP re:dy module sensor."""

    def __init__(self, session, device_json):
        """Initialize the sensor."""
        super().__init__(session, device_json['PKID'],
                         "Power {0}".format(device_json['Name']))

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return 'mdi:flash'

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this sensor."""
        return POWER_WATT

    async def async_update(self):
        """Parse the data for this sensor."""
        if self._id in self._session.modules_dict:
            device_json = self._session.modules_dict[self._id]
            self._parse_data(device_json)
        else:
            self._is_available = False

    def _parse_data(self, data):
        """Parse data received from the server."""
        super()._parse_data(data)

        _LOGGER.debug("Sensor data: %s", str(data))

        for state_var in data['StateVars']:
            if state_var['Name'] == 'ActivePower':
                try:
                    self._state = float(state_var['Value']) * 1000
                except ValueError:
                    _LOGGER.error("Could not parse power for %s", self._id)
                    self._state = 0
                    self._is_available = False
