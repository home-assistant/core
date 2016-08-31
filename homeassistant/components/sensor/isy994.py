"""
Support for ISY994 binary sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.isy994/
"""
import logging

from homeassistant.components.isy994 import (ISYDevice, SENSOR_NODES, ISY)
from homeassistant.const import (TEMP_CELSIUS, TEMP_FAHRENHEIT, STATE_OFF,
                                 STATE_ON)
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

UOM_FRIENDLY_NAME = {
    '1': 'amp',
    '3': 'btu/h',
    '4': TEMP_CELSIUS,
    '5': 'cm',
    '6': 'ft³',
    '7': 'ft³/min',
    '8': 'm³',
    '9': 'day',
    '10': 'days',
    '12': 'dB',
    '13': 'dB A',
    '14': '°',
    '16': 'macroseismic',
    '17': TEMP_FAHRENHEIT,
    '18': 'ft',
    '19': 'hour',
    '20': 'hours',
    '21': 'abs. humidity (%)',
    '22': 'rel. humidity (%)',
    '23': 'inHg',
    '24': 'in/hr',
    '25': 'index',
    '26': 'K',
    '27': 'keyword',
    '28': 'kg',
    '29': 'kV',
    '30': 'kW',
    '31': 'kPa',
    '32': 'KPH',
    '33': 'kWH',
    '34': 'liedu',
    '35': 'l',
    '36': 'lux',
    '37': 'mercalli',
    '38': 'm',
    '39': 'm³/hr',
    '40': 'm/s',
    '41': 'mA',
    '42': 'ms',
    '43': 'mV',
    '44': 'min',
    '45': 'min',
    '46': 'mm/hr',
    '47': 'month',
    '48': 'MPH',
    '49': 'm/s',
    '50': 'ohm',
    '51': '%',
    '52': 'lb',
    '53': 'power factor',
    '54': 'ppm',
    '55': 'pulse count',
    '57': 's',
    '58': 's',
    '59': 'seimens/m',
    '60': 'body wave magnitude scale',
    '61': 'Ricter scale',
    '62': 'moment magnitude scale',
    '63': 'surface wave magnitude scale',
    '64': 'shindo',
    '65': 'SML',
    '69': 'gal',
    '71': 'UV index',
    '72': 'V',
    '73': 'W',
    '74': 'W/m²',
    '75': 'weekday',
    '76': 'Wind Direction (°)',
    '77': 'year',
    '82': 'mm',
    '83': 'km',
    '85': 'ohm',
    '86': 'kOhm',
    '87': 'm³/m³',
    '88': 'Water activity',
    '89': 'RPM',
    '90': 'Hz',
    '91': '° (Relative to North)',
    '92': '° (Relative to South)',
}

UOM_TO_STATES = {
    '11': {
        '0': 'unlocked',
        '100': 'locked',
        '102': 'jammed',
    },
    '15': {
        '1': 'master code changed',
        '2': 'tamper code entry limit',
        '3': 'escutcheon removed',
        '4': 'key/manually locked',
        '5': 'locked by touch',
        '6': 'key/manually unlocked',
        '7': 'remote locking jammed bolt',
        '8': 'remotely locked',
        '9': 'remotely unlocked',
        '10': 'deadbolt jammed',
        '11': 'battery too low to operate',
        '12': 'critical low battery',
        '13': 'low battery',
        '14': 'automatically locked',
        '15': 'automatic locking jammed bolt',
        '16': 'remotely power cycled',
        '17': 'lock handling complete',
        '19': 'user deleted',
        '20': 'user added',
        '21': 'duplicate pin',
        '22': 'jammed bolt by locking with keypad',
        '23': 'locked by keypad',
        '24': 'unlocked by keypad',
        '25': 'keypad attempt outside schedule',
        '26': 'hardware failure',
        '27': 'factory reset'
    },
    '66': {
        '0': 'idle',
        '1': 'heating',
        '2': 'cooling',
        '3': 'fan only',
        '4': 'pending heat',
        '5': 'pending cool',
        '6': 'vent',
        '7': 'aux heat',
        '8': '2nd stage heating',
        '9': '2nd stage cooling',
        '10': '2nd stage aux heat',
        '11': '3rd stage aux heat'
    },
    '67': {
        '0': 'off',
        '1': 'heat',
        '2': 'cool',
        '3': 'auto',
        '4': 'aux/emergency heat',
        '5': 'resume',
        '6': 'fan only',
        '7': 'furnace',
        '8': 'dry air',
        '9': 'moist air',
        '10': 'auto changeover',
        '11': 'energy save heat',
        '12': 'energy save cool',
        '13': 'away'
    },
    '68': {
        '0': 'auto',
        '1': 'on',
        '2': 'auto high',
        '3': 'high',
        '4': 'auto medium',
        '5': 'medium',
        '6': 'circulation',
        '7': 'humidity circulation'
    },
    '93': {
        '1': 'power applied',
        '2': 'ac mains disconnected',
        '3': 'ac mains reconnected',
        '4': 'surge detection',
        '5': 'volt drop or drift',
        '6': 'over current detected',
        '7': 'over voltage detected',
        '8': 'over load detected',
        '9': 'load error',
        '10': 'replace battery soon',
        '11': 'replace battery now',
        '12': 'battery is charging',
        '13': 'battery is fully charged',
        '14': 'charge battery soon',
        '15': 'charge battery now'
    },
    '94': {
        '1': 'program started',
        '2': 'program in progress',
        '3': 'program completed',
        '4': 'replace main filter',
        '5': 'failure to set target temperature',
        '6': 'supplying water',
        '7': 'water supply failure',
        '8': 'boiling',
        '9': 'boiling failure',
        '10': 'washing',
        '11': 'washing failure',
        '12': 'rinsing',
        '13': 'rinsing failure',
        '14': 'draining',
        '15': 'draining failure',
        '16': 'spinning',
        '17': 'spinning failure',
        '18': 'drying',
        '19': 'drying failure',
        '20': 'fan failure',
        '21': 'compressor failure'
    },
    '95': {
        '1': 'leaving bed',
        '2': 'sitting on bed',
        '3': 'lying on bed',
        '4': 'posture changed',
        '5': 'sitting on edge of bed'
    },
    '96': {
        '1': 'clean',
        '2': 'slightly polluted',
        '3': 'moderately polluted',
        '4': 'highly polluted'
    },
    '97': {
        '0': 'closed',
        '100': 'open',
        '102': 'stopped',
        '103': 'closing',
        '104': 'opening'
    }
}

BINARY_UOM = ['2', '78']


def setup_platform(hass, config: ConfigType, add_devices, discovery_info=None):
    """Setup the ISY platform."""

    if ISY is None or not ISY.connected:
        _LOGGER.error('A connection has not been made to the ISY controller.')
        return False

    devices = []

    for node in SENSOR_NODES:
        if node.uom not in BINARY_UOM and \
                STATE_OFF not in node.uom and STATE_ON not in node.uom:
            devices.append(ISYSensorDevice(node))

    add_devices(devices)


class ISYSensorDevice(ISYDevice):
    """Representation of a ISY sensor."""

    def __init__(self, node):
        """Initialize the sensor."""
        ISYDevice.__init__(self, node)

    @property
    def state(self) -> str:
        """Return the state of the device."""
        if len(self._node.uom) == 1:
            return self.value
        elif self._node.uom in UOM_TO_STATES:
            states = UOM_TO_STATES.get(self._node.uom)
            if self.value in states:
                return states.get(self.value)

        return None

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement for the device."""
        if len(self._node.uom) == 1:
            if self._node.uom in UOM_FRIENDLY_NAME:
                return UOM_FRIENDLY_NAME.get(self._node.uom)
            else:
                return self._node.uom
        else:
            return None
