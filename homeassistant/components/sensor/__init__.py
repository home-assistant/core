"""
homeassistant.components.sensor
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Component to interface with various sensors that can be monitored.
"""
import logging

from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.components import wink, zwave, isy994

DOMAIN = 'sensor'
DEPENDENCIES = []
SCAN_INTERVAL = 30

ENTITY_ID_FORMAT = DOMAIN + '.{}'

DISCOVER_CHILD_SENSORS = 'sensor.child_sensors'
DISCOVER_VERA_SENSORS = 'vera.sensors'

# Maps discovered services to their platforms
DISCOVERY_PLATFORMS = {
    wink.DISCOVER_SENSORS: 'wink',
    zwave.DISCOVER_SENSORS: 'zwave',
    isy994.DISCOVER_SENSORS: 'isy994',
    DISCOVER_CHILD_SENSORS: 'child_sensor',
    DISCOVER_VERA_SENSORS: 'vera'
}


def setup(hass, config):
    """ Track states and offer events for sensors. """
    component = EntityComponent(
        logging.getLogger(__name__), DOMAIN, hass, SCAN_INTERVAL,
        DISCOVERY_PLATFORMS)

    component.setup(config)

    return True
