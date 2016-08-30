"""
Sensors of a KNX Device.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/knx/
"""
from homeassistant.const import (TEMP_CELSIUS, TEMPERATURE, CONF_TYPE,
                                 ILLUMINANCE, SPEED_MS, CONF_MINIMUM,
                                 CONF_MAXIMUM)
from homeassistant.components.knx import (KNXConfig, KNXGroupAddress)


DEPENDENCIES = ["knx"]

# Speed units
SPEED_METERPERSECOND = "m/s"  # type: str

# Illuminance units
ILLUMINANCE_LUX = "lx"  # type: str

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


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Setup the KNX Sensor platform."""
    # Add KNX Temperature Sensors
    # KNX Datapoint 9.001 DPT_Value_Temp
    if config[CONF_TYPE] == TEMPERATURE:
        minimum_value, maximum_value = \
            update_and_define_min_max(config, KNX_TEMP_MIN,
                                      KNX_TEMP_MAX)

        add_entities([
            KNXSensorFloatClass(hass, KNXConfig(config), TEMP_CELSIUS,
                                minimum_value, maximum_value)
        ])

    # Add KNX Speed Sensors(Like Wind Speed)
    # KNX Datapoint 9.005 DPT_Value_Wsp
    elif config[CONF_TYPE] == SPEED_MS:
        minimum_value, maximum_value = \
            update_and_define_min_max(config, KNX_SPEED_MS_MIN,
                                      KNX_SPEED_MS_MAX)

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


def update_and_define_min_max(config, minimum_default,
                              maximum_default):
    """Function help determinate a min/max value defined in config."""
    minimum_value = minimum_default
    maximum_value = maximum_default
    if config.get(CONF_MINIMUM):
        minimum_value = config.get(CONF_MINIMUM)

    if config.get(CONF_MAXIMUM):
        maximum_value = config.get(CONF_MAXIMUM)

    return minimum_value, maximum_value


class KNXSensorBaseClass():  # pylint: disable=too-few-public-methods
    """Sensor Base Class for all KNX Sensors."""

    _unit_of_measurement = None

    @property
    def cache(self):
        """We don't want to cache any Sensor Value."""
        return False

    @property
    def unit_of_measurement(self):
        """Return the defined Unit of Measurement for the KNX Sensor."""
        return self._unit_of_measurement


class KNXSensorFloatClass(KNXGroupAddress, KNXSensorBaseClass):
    """
    Base Implementation of a 2byte Floating Point KNX Telegram.

    Defined in KNX 3.7.2 - 3.10
    """

    # pylint: disable=too-many-arguments
    def __init__(self, hass, config, unit_of_measurement, minimum_sensor_value,
                 maximum_sensor_value):
        """Initialize a KNX Float Sensor."""
        self._unit_of_measurement = unit_of_measurement
        self._minimum_value = minimum_sensor_value
        self._maximum_value = maximum_sensor_value

        KNXGroupAddress.__init__(self, hass, config)

    @property
    def state(self):
        """Return the Value of the KNX Sensor."""
        if self._data:
            from knxip.conversion import knx2_to_float
            value = knx2_to_float(self._data)
            if self._minimum_value <= value <= self._maximum_value:
                return value
        return None
