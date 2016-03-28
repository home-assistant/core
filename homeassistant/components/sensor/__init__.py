"""
Component to interface with various sensors that can be monitored.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/sensor/
"""
import logging

from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA  # noqa
from homeassistant.components import (
    wink, zwave, isy994, verisure, ecobee, tellduslive, mysensors,
    bloomsky, vera)

DOMAIN = 'sensor'
SCAN_INTERVAL = 30

ENTITY_ID_FORMAT = DOMAIN + '.{}'

# Maps discovered services to their platforms
DISCOVERY_PLATFORMS = {
    bloomsky.DISCOVER_SENSORS: 'bloomsky',
    wink.DISCOVER_SENSORS: 'wink',
    zwave.DISCOVER_SENSORS: 'zwave',
    isy994.DISCOVER_SENSORS: 'isy994',
    verisure.DISCOVER_SENSORS: 'verisure',
    ecobee.DISCOVER_SENSORS: 'ecobee',
    tellduslive.DISCOVER_SENSORS: 'tellduslive',
    mysensors.DISCOVER_SENSORS: 'mysensors',
    vera.DISCOVER_SENSORS: 'vera',
}


def setup(hass, config):
    """Track states and offer events for sensors."""
    component = EntityComponent(
        logging.getLogger(__name__), DOMAIN, hass, SCAN_INTERVAL,
        DISCOVERY_PLATFORMS)

    component.setup(config)

    return True
