"""
homeassistant.components.tellstick_sensor
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Shows sensor values from tellstick sensors.

Possible config keys:

id of the sensor: Name the sensor with ID
135=Outside

only_named: Only show the named sensors
only_named=1

temperature_scale: The scale of the temperature value
temperature_scale=°C

datatype_mask: mask to determine which sensor values to show based on
https://tellcore-py.readthedocs.org
    /en/v1.0.4/constants.html#module-tellcore.constants

datatype_mask=1   # only show temperature
datatype_mask=12  # only show rain rate and rain total
datatype_mask=127 # show all sensor values
"""
import logging
from collections import namedtuple

import homeassistant.util as util
from homeassistant.const import ATTR_FRIENDLY_NAME, ATTR_UNIT_OF_MEASUREMENT

# The domain of your component. Should be equal to the name of your component
DOMAIN = "tellstick_sensor"

# List of component names (string) your component depends upon
# If you are setting up a group but not using a group for anything,
# don't depend on group
DEPENDENCIES = []

ENTITY_ID_FORMAT = DOMAIN + '.{}'

DatatypeDescription = namedtuple("DatatypeDescription", ['name', 'unit'])


def setup(hass, config):
    """ Register services or listen for events that your component needs. """

    logger = logging.getLogger(__name__)

    try:
        import tellcore.telldus as telldus
        import tellcore.constants as tellcore_constants
    except ImportError:
        logger.exception(
            "Failed to import tellcore")
        return False

    core = telldus.TelldusCore()

    sensors = core.sensors()

    if len(sensors) == 0:
        logger.error("No Tellstick sensors found")
        return False

    sensor_value_descriptions = {
        tellcore_constants.TELLSTICK_TEMPERATURE:
        DatatypeDescription(
            'temperature', config[DOMAIN]['temperature_scale']),

        tellcore_constants.TELLSTICK_HUMIDITY:
        DatatypeDescription('humidity', ' %'),

        tellcore_constants.TELLSTICK_RAINRATE:
        DatatypeDescription('rain rate', ''),

        tellcore_constants.TELLSTICK_RAINTOTAL:
        DatatypeDescription('rain total', ''),

        tellcore_constants.TELLSTICK_WINDDIRECTION:
        DatatypeDescription('wind direction', ''),

        tellcore_constants.TELLSTICK_WINDAVERAGE:
        DatatypeDescription('wind average', ''),

        tellcore_constants.TELLSTICK_WINDGUST:
        DatatypeDescription('wind gust', '')
    }

    def update_sensor_value_state(sensor_name, sensor_value):
        """ Update the state of a sensor value """
        sensor_value_description = \
            sensor_value_descriptions[sensor_value.datatype]
        sensor_value_name = '{} {}'.format(
            sensor_name, sensor_value_description.name)

        entity_id = ENTITY_ID_FORMAT.format(
            util.slugify(sensor_value_name))

        state = sensor_value.value

        state_attr = {
            ATTR_FRIENDLY_NAME: sensor_value_name,
            ATTR_UNIT_OF_MEASUREMENT: sensor_value_description.unit
        }

        hass.states.set(entity_id, state, state_attr)

    sensor_value_datatypes = [
        tellcore_constants.TELLSTICK_TEMPERATURE,
        tellcore_constants.TELLSTICK_HUMIDITY,
        tellcore_constants.TELLSTICK_RAINRATE,
        tellcore_constants.TELLSTICK_RAINTOTAL,
        tellcore_constants.TELLSTICK_WINDDIRECTION,
        tellcore_constants.TELLSTICK_WINDAVERAGE,
        tellcore_constants.TELLSTICK_WINDGUST
    ]

    def update_sensor_state(sensor):
        """ Updates all the sensor values from the sensor """
        try:
            sensor_name = config[DOMAIN][str(sensor.id)]
        except KeyError:
            if 'only_named' in config[DOMAIN]:
                return
            sensor_name = str(sensor.id)

        for datatype in sensor_value_datatypes:
            if datatype & int(config[DOMAIN]['datatype_mask']) and \
                    sensor.has_value(datatype):
                update_sensor_value_state(sensor_name, sensor.value(datatype))

    # pylint: disable=unused-argument
    def update_sensors_state(time):
        """ Update the state of all sensors """
        for sensor in sensors:
            update_sensor_state(sensor)

    update_sensors_state(None)

    hass.track_time_change(update_sensors_state, second=[0, 30])

    return True
