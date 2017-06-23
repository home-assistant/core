"""
Sensors of a KNX Device.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/knx/
"""
from homeassistant.const import (
    TEMP_CELSIUS, TEMPERATURE, CONF_TYPE, ILLUMINANCE, SPEED_MS, CONF_MINIMUM,
    CONF_MAXIMUM)
from homeassistant.components.knx import (KNXConfig, KNXGroupAddress)

DEPENDENCIES = ['knx']

# Speed units
SPEED_METERPERSECOND = 'm/s'  # type: str

# Illuminance units
ILLUMINANCE_LUX = 'lx'  # type: str

# Percentage units
PERCENTAGE_UNIT = "%"

#  Predefined Minimum, Maximum Values for Sensors
#  Temperature as defined in KNX Standard 3.10 - 9.001 DPT_Value_Temp
KNX_TEMP_MIN = -273
KNX_TEMP_MAX = 670760

#  Luminance(LUX) as Defined in KNX Standard 3.10 - 9.004 DPT_Value_Lux
KNX_LUX_MIN = 0
KNX_LUX_MAX = 670760

#  Speed m/s as defined in KNX Standard 3.10 - 9.005 DPT_Value_Wsp
KNX_SPEED_MS_MIN = 0
KNX_SPEED_MS_MAX = 670760

# Configuration string for percentage
PERCENTAGE = 'percentage'


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the KNX Sensor platform."""
    # KNX Datapoint 9.001 DPT_Value_Temp
    if config[CONF_TYPE] == TEMPERATURE:
        minimum_value, maximum_value = \
            update_and_define_min_max(config, KNX_TEMP_MIN, KNX_TEMP_MAX)

        add_entities([
            KNXSensorFloatClass(
                hass, KNXConfig(config), TEMP_CELSIUS, minimum_value,
                maximum_value)
        ])

    # Add KNX Speed Sensors(Like Wind Speed)
    # KNX Datapoint 9.005 DPT_Value_Wsp
    elif config[CONF_TYPE] == SPEED_MS:
        minimum_value, maximum_value = \
            update_and_define_min_max(
                config, KNX_SPEED_MS_MIN, KNX_SPEED_MS_MAX)

        add_entities([
            KNXSensorFloatClass(hass, KNXConfig(config), SPEED_METERPERSECOND,
                                minimum_value, maximum_value)
        ])

    # Add KNX Illuminance Sensors(Lux)
    # KNX Datapoint 9.004 DPT_Value_Lux
    elif config[CONF_TYPE] == ILLUMINANCE:
        minimum_value, maximum_value = \
            update_and_define_min_max(config, KNX_LUX_MIN, KNX_LUX_MAX)

        add_entities([
            KNXSensorFloatClass(hass, KNXConfig(config), ILLUMINANCE_LUX,
                                minimum_value, maximum_value)
        ])
    # Add KNX Percentage Sensors(%)
    # KNX Datapoint 5.001 DPT_Scaling
    elif config[CONF_TYPE] == PERCENTAGE:
        minimum_value, maximum_value = \
            update_and_define_min_max(config, 0, 100)

        add_entities([
            KNXSensorDPTScalingClass(hass, KNXConfig(config), PERCENTAGE_UNIT,
                                     minimum_value, maximum_value)
        ])


def update_and_define_min_max(config, minimum_default, maximum_default):
    """Determine a min/max value defined in the configuration."""
    minimum_value = minimum_default
    maximum_value = maximum_default
    if config.get(CONF_MINIMUM):
        minimum_value = config.get(CONF_MINIMUM)

    if config.get(CONF_MAXIMUM):
        maximum_value = config.get(CONF_MAXIMUM)

    return minimum_value, maximum_value


class KNXSensorBaseClass(KNXGroupAddress):
    """Sensor Base Class for all KNX Sensors."""

    def __init__(self, hass, config, unit_of_measurement, minimum_sensor_value,
                 maximum_sensor_value):
        """Initialize a KNX Float Sensor."""
        self._unit_of_measurement = unit_of_measurement
        self._minimum_value = minimum_sensor_value
        self._maximum_value = maximum_sensor_value
        self._value = None

        KNXGroupAddress.__init__(self, hass, config)

    @property
    def state(self):
        """Return the Value of the KNX Sensor."""
        return self._value

    @property
    def unit_of_measurement(self):
        """Return the defined Unit of Measurement for the KNX Sensor."""
        return self._unit_of_measurement

    def convert(self, raw_value):
        """Convert value of data point.

        This should be overriden in derived classes
        """
        pass

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


class KNXSensorFloatClass(KNXSensorBaseClass):
    """
    Base Implementation of a 2byte Floating Point KNX Telegram.

    Defined in KNX 3.7.2 - 3.10
    """

    def convert(self, raw_value):
        """Conversion for 2 byte floating point values."""
        from knxip.conversion import knx2_to_float

        return knx2_to_float(raw_value)


class KNXSensorDPTScalingClass(KNXSensorBaseClass):
    """
    Base Implementation of a 1byte percentage scaled KNX Telegram.

    Defined in KNX 3.7.2 - 3.10
    """

    def convert(self, raw_value):
        """Conversion for scaled byte values."""
        summed_value = 0
        try:
            # convert raw value in bytes
            for val in raw_value:
                summed_value *= 256
                summed_value += val
        except TypeError:
            # pknx returns a non-iterable type for unsuccessful reads
            pass

        return round(summed_value * 100 / 255)
