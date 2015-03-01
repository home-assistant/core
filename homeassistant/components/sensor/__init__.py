"""
homeassistant.components.sensor
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Component to interface with various sensors that can be monitored.
"""
import logging
from datetime import timedelta

from homeassistant.loader import get_component
import homeassistant.util as util
from homeassistant.helpers import (
    platform_devices_from_config, generate_entity_id)
from homeassistant.components import discovery, wink, zwave

DOMAIN = 'sensor'
DEPENDENCIES = []

ENTITY_ID_FORMAT = DOMAIN + '.{}'

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=1)

# Maps discovered services to their platforms
DISCOVERY_PLATFORMS = {
    wink.DISCOVER_SENSORS: 'wink',
    zwave.DISCOVER_SENSORS: 'zwave',
}

_LOGGER = logging.getLogger(__name__)


def setup(hass, config):
    """ Track states and offer events for sensors. """
    logger = logging.getLogger(__name__)

    sensors = platform_devices_from_config(
        config, DOMAIN, hass, ENTITY_ID_FORMAT, logger)

    @util.Throttle(MIN_TIME_BETWEEN_SCANS)
    def update_sensor_states(now):
        """ Update states of all sensors. """
        if sensors:
            for sensor in sensors.values():
                if sensor.should_poll:
                    sensor.update_ha_state(True)

    update_sensor_states(None)

    def sensor_discovered(service, info):
        """ Called when a sensor is discovered. """
        platform = get_component("{}.{}".format(
            DOMAIN, DISCOVERY_PLATFORMS[service]))

        discovered = platform.devices_discovered(hass, config, info)

        for sensor in discovered:
            if sensor is not None and sensor not in sensors.values():
                sensor.hass = hass

                sensor.entity_id = generate_entity_id(
                    ENTITY_ID_FORMAT, sensor.name, sensors.keys())

                sensors[sensor.entity_id] = sensor

                sensor.update_ha_state()

    discovery.listen(hass, DISCOVERY_PLATFORMS.keys(), sensor_discovered)

    # Fire every 3 seconds
    hass.track_time_change(update_sensor_states, second=range(0, 60, 3))

    return True
