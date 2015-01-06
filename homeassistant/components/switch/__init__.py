"""
homeassistant.components.switch
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Component to interface with various switches that can be controlled remotely.
"""
import logging
from datetime import timedelta

import homeassistant.util as util
from homeassistant.const import (
    STATE_ON, SERVICE_TURN_ON, SERVICE_TURN_OFF, ATTR_ENTITY_ID)
from homeassistant.helpers import (
    extract_entity_ids, platform_devices_from_config)
from homeassistant.components import group

DOMAIN = 'switch'
DEPENDENCIES = []

GROUP_NAME_ALL_SWITCHES = 'all_switches'
ENTITY_ID_ALL_SWITCHES = group.ENTITY_ID_FORMAT.format(
    GROUP_NAME_ALL_SWITCHES)

ENTITY_ID_FORMAT = DOMAIN + '.{}'

ATTR_TODAY_MWH = "today_mwh"
ATTR_CURRENT_POWER_MWH = "current_power_mwh"

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

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
    logger = logging.getLogger(__name__)

    switches = platform_devices_from_config(
        config, DOMAIN, hass, ENTITY_ID_FORMAT, logger)

    if not switches:
        return False

    # pylint: disable=unused-argument
    @util.Throttle(MIN_TIME_BETWEEN_SCANS)
    def update_states(now):
        """ Update states of all switches. """

        logger.info("Updating switch states")

        for switch in switches.values():
            switch.update_ha_state(hass)

    update_states(None)

    def handle_switch_service(service):
        """ Handles calls to the switch services. """
        target_switches = [switches[entity_id] for entity_id
                           in extract_entity_ids(hass, service)
                           if entity_id in switches]

        if not target_switches:
            target_switches = switches.values()

        for switch in target_switches:
            if service.service == SERVICE_TURN_ON:
                switch.turn_on()
            else:
                switch.turn_off()

            switch.update_ha_state(hass)

    # Track all switches in a group
    group.setup_group(hass, GROUP_NAME_ALL_SWITCHES,
                      switches.keys(), False)

    # Update state every 30 seconds
    hass.track_time_change(update_states, second=[0, 30])

    hass.services.register(DOMAIN, SERVICE_TURN_OFF, handle_switch_service)

    hass.services.register(DOMAIN, SERVICE_TURN_ON, handle_switch_service)

    return True
