"""
homeassistant.components.sensor
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Component to interface with various sensors that can be monitored.
"""
import logging

from homeassistant.helpers.device_component import DeviceComponent
from homeassistant.components import wink, zwave

DOMAIN = 'sensor'
DEPENDENCIES = []
SCAN_INTERVAL = 30

ENTITY_ID_FORMAT = DOMAIN + '.{}'

# Maps discovered services to their platforms
DISCOVERY_PLATFORMS = {
    wink.DISCOVER_SENSORS: 'wink',
    zwave.DISCOVER_SENSORS: 'zwave',
}


def setup(hass, config):
    """ Track states and offer events for sensors. """
    component = DeviceComponent(
        logging.getLogger(__name__), DOMAIN, hass, SCAN_INTERVAL,
        DISCOVERY_PLATFORMS)

    component.setup(config)

    return True
