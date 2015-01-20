"""
homeassistant.components.sensor
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Component to interface with various sensors that can be monitored.
"""
import logging
from datetime import timedelta

from homeassistant.loader import get_component
import homeassistant.util as util
from homeassistant.const import (
    STATE_OPEN, STATE_CLOSED, ATTR_ENTITY_ID)
from homeassistant.helpers import (
    extract_entity_ids, platform_devices_from_config)
from homeassistant.components import group, discovery, wink

DOMAIN = 'sensor'
DEPENDENCIES = []

GROUP_NAME_ALL_SENSORS = 'all_sensors'
ENTITY_ID_ALL_SENSORS = group.ENTITY_ID_FORMAT.format(
    GROUP_NAME_ALL_SENSORS)

ENTITY_ID_FORMAT = DOMAIN + '.{}'

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

# Maps discovered services to their platforms
DISCOVERY_PLATFORMS = {
    wink.DISCOVER_SENSORS: 'wink',
}

_LOGGER = logging.getLogger(__name__)


def is_on(hass, entity_id=None):
    """ Returns if the sensor is open based on the statemachine. """
    entity_id = entity_id or ENTITY_ID_ALL_SENSORS

    return hass.states.is_state(entity_id, STATE_OPEN)

def setup(hass, config):
    """ Track states and offer events for sensors. """
    logger = logging.getLogger(__name__)

    sensors = platform_devices_from_config(
        config, DOMAIN, hass, ENTITY_ID_FORMAT, logger)

    # pylint: disable=unused-argument
    @util.Throttle(MIN_TIME_BETWEEN_SCANS)
    def update_states(now):
        """ Update states of all sensors. """
        if sensors:
            logger.info("Updating sensor states")

            for sensor in sensors.values():
                sensor.update_ha_state(hass, True)

    update_states(None)

    # Track all sensors in a group
    sensor_group = group.Group(
        hass, GROUP_NAME_ALL_SENSORS, sensors.keys(), False)

    def sensor_discovered(service, info):
        """ Called when a sensor is discovered. """
        platform = get_component("{}.{}".format(
            DOMAIN, DISCOVERY_PLATFORMS[service]))

        discovered = platform.devices_discovered(hass, config, info)

        for sensor in discovered:
            if sensor is not None and sensor not in sensors.values():
                sensor.entity_id = util.ensure_unique_string(
                    ENTITY_ID_FORMAT.format(util.slugify(sensor.name)),
                    sensors.keys())

                sensors[sensor.entity_id] = sensor

                sensor.update_ha_state(hass)

        sensor_group.update_tracked_entity_ids(sensors.keys())

    discovery.listen(hass, DISCOVERY_PLATFORMS.keys(), sensor_discovered)

    hass.track_time_change(update_states)

    return True
