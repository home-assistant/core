"""
Sensors of a KNX Device.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/knx/
"""
from enum import Enum

import logging
import voluptuous as vol

from homeassistant.const import (
    CONF_NAME, CONF_MAXIMUM, CONF_MINIMUM,
    CONF_TYPE, TEMP_CELSIUS
)
from homeassistant.components.knx import (KNXConfig, KNXGroupAddress)
from homeassistant.components.sensor import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['knx']

DEFAULT_NAME = "KNX sensor"

CONF_TEMPERATURE = 'temperature'
CONF_ADDRESS = 'address'
CONF_ILLUMINANCE = 'illuminance'
CONF_PERCENTAGE = 'percentage'
CONF_SPEED_MS = 'speed_ms'


class KNXAddressType(Enum):
    """Enum to indicate conversion type for the KNX address."""

    FLOAT = 1
    PERCENT = 2


# define the fixed settings required for each sensor type
FIXED_SETTINGS_MAP = {
    #  Temperature as defined in KNX Standard 3.10 - 9.001 DPT_Value_Temp
    CONF_TEMPERATURE: {
        'unit': TEMP_CELSIUS,
        'default_minimum': -273,
        'default_maximum': 670760,
        'address_type': KNXAddressType.FLOAT
    },
    #  Speed m/s as defined in KNX Standard 3.10 - 9.005 DPT_Value_Wsp
    CONF_SPEED_MS: {
        'unit': 'm/s',
        'default_minimum': 0,
        'default_maximum': 670760,
        'address_type': KNXAddressType.FLOAT
    },
    #  Luminance(LUX) as defined in KNX Standard 3.10 - 9.004 DPT_Value_Lux
    CONF_ILLUMINANCE: {
        'unit': 'lx',
        'default_minimum': 0,
        'default_maximum': 670760,
        'address_type': KNXAddressType.FLOAT
    },
    #  Percentage(%) as defined in KNX Standard 3.10 - 5.001 DPT_Scaling
    CONF_PERCENTAGE: {
        'unit': '%',
        'default_minimum': 0,
        'default_maximum': 100,
        'address_type': KNXAddressType.PERCENT
    }
}

SENSOR_TYPES = set(FIXED_SETTINGS_MAP.keys())

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_TYPE): vol.In(SENSOR_TYPES),
    vol.Required(CONF_ADDRESS): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_MINIMUM): vol.Coerce(float),
    vol.Optional(CONF_MAXIMUM): vol.Coerce(float)
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the KNX Sensor platform."""
    add_devices([KNXSensor(hass, KNXConfig(config))])


class KNXSensor(KNXGroupAddress):
    """Representation of a KNX Sensor device."""

    def __init__(self, hass, config):
        """Initialize a KNX Float Sensor."""
        # set up the KNX Group address
        KNXGroupAddress.__init__(self, hass, config)

        device_type = config.config.get(CONF_TYPE)
        sensor_config = FIXED_SETTINGS_MAP.get(device_type)

        if not sensor_config:
            raise NotImplementedError()

        # set up the conversion function based on the address type
        address_type = sensor_config.get('address_type')
        if address_type == KNXAddressType.FLOAT:
            self.convert = convert_float
        elif address_type == KNXAddressType.PERCENT:
            self.convert = convert_percent
        else:
            raise NotImplementedError()

        # other settings
        self._unit_of_measurement = sensor_config.get('unit')
        default_min = float(sensor_config.get('default_minimum'))
        default_max = float(sensor_config.get('default_maximum'))
        self._minimum_value = config.config.get(CONF_MINIMUM, default_min)
        self._maximum_value = config.config.get(CONF_MAXIMUM, default_max)
        _LOGGER.debug(
            "%s: configured additional settings: unit=%s, "
            "min=%f, max=%f, type=%s",
            self.name, self._unit_of_measurement,
            self._minimum_value, self._maximum_value, str(address_type)
        )

        self._value = None

    @property
    def state(self):
        """Return the Value of the KNX Sensor."""
        return self._value

    @property
    def unit_of_measurement(self):
        """Return the defined Unit of Measurement for the KNX Sensor."""
        return self._unit_of_measurement

    def update(self):
        """Update KNX sensor."""
        super().update()

        self._value = None

        if self._data:
            if self._data == 0:
                value = 0
            else:
                value = self.convert(self._data)
            if self._minimum_value <= value <= self._maximum_value:
                self._value = value

    @property
    def cache(self):
        """We don't want to cache any Sensor Value."""
        return False


def convert_float(raw_value):
    """Conversion for 2 byte floating point values.

    2byte Floating Point KNX Telegram.
    Defined in KNX 3.7.2 - 3.10
    """
    from knxip.conversion import knx2_to_float
    from knxip.core import KNXException

    try:
        return knx2_to_float(raw_value)
    except KNXException as exception:
        _LOGGER.error("Can't convert %s to float (%s)", raw_value, exception)


def convert_percent(raw_value):
    """Conversion for scaled byte values.

    1byte percentage scaled KNX Telegram.
    Defined in KNX 3.7.2 - 3.10.
    """
    value = 0
    try:
        value = raw_value[0]
    except (IndexError, ValueError):
        # pknx returns a non-iterable type for unsuccessful reads
        _LOGGER.error("Can't convert %s to percent value", raw_value)

    return round(value * 100 / 255)
