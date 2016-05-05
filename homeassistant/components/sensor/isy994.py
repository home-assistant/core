"""
Support for ISY994 sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/isy994/
"""
import logging

from homeassistant.components.isy994 import (
    HIDDEN_STRING, ISY, SENSOR_STRING, ISYDeviceABC)
from homeassistant.const import (
    STATE_CLOSED, STATE_HOME, STATE_NOT_HOME, STATE_OFF, STATE_ON, STATE_OPEN)

DEFAULT_HIDDEN_WEATHER = ['Temperature_High', 'Temperature_Low', 'Feels_Like',
                          'Temperature_Average', 'Pressure', 'Dew_Point',
                          'Gust_Speed', 'Evapotranspiration',
                          'Irrigation_Requirement', 'Water_Deficit_Yesterday',
                          'Elevation', 'Average_Temperature_Tomorrow',
                          'High_Temperature_Tomorrow',
                          'Low_Temperature_Tomorrow', 'Humidity_Tomorrow',
                          'Wind_Speed_Tomorrow', 'Gust_Speed_Tomorrow',
                          'Rain_Tomorrow', 'Snow_Tomorrow',
                          'Forecast_Average_Temperature',
                          'Forecast_High_Temperature',
                          'Forecast_Low_Temperature', 'Forecast_Humidity',
                          'Forecast_Rain', 'Forecast_Snow']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the ISY994 platform."""
    # pylint: disable=protected-access
    logger = logging.getLogger(__name__)
    devs = []
    # Verify connection
    if ISY is None or not ISY.connected:
        logger.error('A connection has not been made to the ISY controller.')
        return False

    # Import weather
    if ISY.climate is not None:
        for prop in ISY.climate._id2name:
            if prop is not None:
                prefix = HIDDEN_STRING \
                    if prop in DEFAULT_HIDDEN_WEATHER else ''
                node = WeatherPseudoNode('ISY.weather.' + prop, prefix + prop,
                                         getattr(ISY.climate, prop),
                                         getattr(ISY.climate, prop + '_units'))
                devs.append(ISYSensorDevice(node))

    # Import sensor nodes
    for (path, node) in ISY.nodes:
        if SENSOR_STRING in node.name:
            if HIDDEN_STRING in path:
                node.name += HIDDEN_STRING
            devs.append(ISYSensorDevice(node, [STATE_ON, STATE_OFF]))

    # Import sensor programs
    for (folder_name, states) in (
            ('HA.locations', [STATE_HOME, STATE_NOT_HOME]),
            ('HA.sensors', [STATE_OPEN, STATE_CLOSED]),
            ('HA.states', [STATE_ON, STATE_OFF])):
        try:
            folder = ISY.programs['My Programs'][folder_name]
        except KeyError:
            # folder does not exist
            pass
        else:
            for _, _, node_id in folder.children:
                node = folder[node_id].leaf
                devs.append(ISYSensorDevice(node, states))

    add_devices(devs)


class WeatherPseudoNode(object):
    """This class allows weather variable to act as regular nodes."""

    # pylint: disable=too-few-public-methods
    def __init__(self, device_id, name, status, units=None):
        """Initialize the sensor."""
        self._id = device_id
        self.name = name
        self.status = status
        self.units = units


class ISYSensorDevice(ISYDeviceABC):
    """Representation of an ISY sensor."""

    _domain = 'sensor'

    def __init__(self, node, states=None):
        """Initialize the device."""
        super().__init__(node)
        self._states = states or []
