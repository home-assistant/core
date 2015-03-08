"""
homeassistant.components.switch
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Component to interface with various switches that can be controlled remotely.
"""
import logging
from datetime import timedelta

from homeassistant.helpers.device_component import DeviceComponent

from homeassistant.const import (
    STATE_ON, SERVICE_TURN_ON, SERVICE_TURN_OFF, ATTR_ENTITY_ID)
from homeassistant.components import group, discovery, wink

DOMAIN = 'switch'
DEPENDENCIES = []
SCAN_INTERVAL = 30

GROUP_NAME_ALL_SWITCHES = 'all switches'
ENTITY_ID_ALL_SWITCHES = group.ENTITY_ID_FORMAT.format('all_switches')

ENTITY_ID_FORMAT = DOMAIN + '.{}'

ATTR_TODAY_MWH = "today_mwh"
ATTR_CURRENT_POWER_MWH = "current_power_mwh"

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

# Maps discovered services to their platforms
DISCOVERY_PLATFORMS = {
    discovery.services.BELKIN_WEMO: 'wemo',
    wink.DISCOVER_SWITCHES: 'wink',
}

_LOGGER = logging.getLogger(__name__)


def is_on(hass, entity_id=None):
    """ Returns if the switch is on based on the statemachine. """
    entity_id = entity_id or ENTITY_ID_ALL_SWITCHES

    return hass.states.is_state(entity_id, STATE_ON)


def turn_on(hass, entity_id=None):
    """ Turns all or specified switch on. """
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None

    hass.services.call(DOMAIN, SERVICE_TURN_ON, data)


def turn_off(hass, entity_id=None):
    """ Turns all or specified switch off. """
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None

    hass.services.call(DOMAIN, SERVICE_TURN_OFF, data)


def setup(hass, config):
    """ Track states and offer events for switches. """
    component = DeviceComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL, DISCOVERY_PLATFORMS,
        GROUP_NAME_ALL_SWITCHES)
    component.setup(config)

    def handle_switch_service(service):
        """ Handles calls to the switch services. """
        target_switches = component.extract_from_service(service)

        for switch in target_switches:
            if service.service == SERVICE_TURN_ON:
                switch.turn_on()
            else:
                switch.turn_off()

            switch.update_ha_state(True)

    hass.services.register(DOMAIN, SERVICE_TURN_OFF, handle_switch_service)

    hass.services.register(DOMAIN, SERVICE_TURN_ON, handle_switch_service)

    return True
