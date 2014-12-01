"""
homeassistant.components.switch
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Component to interface with various switches that can be controlled remotely.
"""
import logging
from datetime import datetime, timedelta

import homeassistant as ha
import homeassistant.util as util
from homeassistant.loader import get_component
from homeassistant.components import (
    group, extract_entity_ids, STATE_ON,
    SERVICE_TURN_ON, SERVICE_TURN_OFF, ATTR_ENTITY_ID)

DOMAIN = 'switch'
DEPENDENCIES = []

GROUP_NAME_ALL_SWITCHES = 'all_switches'
ENTITY_ID_ALL_SWITCHES = group.ENTITY_ID_FORMAT.format(
    GROUP_NAME_ALL_SWITCHES)

ENTITY_ID_FORMAT = DOMAIN + '.{}'

ATTR_TODAY_KWH = "today_kwh"
ATTR_CURRENT_POWER = "current_power"
ATTR_TODAY_ON_TIME = "today_on_time"
ATTR_TODAY_STANDBY_TIME = "today_standby_time"

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


# pylint: disable=too-many-branches
def setup(hass, config):
    """ Track states and offer events for switches. """
    logger = logging.getLogger(__name__)

    if not util.validate_config(config, {DOMAIN: [ha.CONF_TYPE]}, logger):
        return False

    switch_type = config[DOMAIN][ha.CONF_TYPE]

    switch_init = get_component('switch.{}'.format(switch_type))

    if switch_init is None:
        logger.error("Error loading switch component %s", switch_type)

        return False

    switches = switch_init.get_switches(hass, config[DOMAIN])

    if len(switches) == 0:
        logger.error("No switches found")
        return False

    # Setup a dict mapping entity IDs to devices
    ent_to_switch = {}

    no_name_count = 1

    for switch in switches:
        name = switch.get_name()

        if name is None:
            name = "Switch #{}".format(no_name_count)
            no_name_count += 1

        entity_id = util.ensure_unique_string(
            ENTITY_ID_FORMAT.format(util.slugify(name)),
            list(ent_to_switch.keys()))

        switch.entity_id = entity_id
        ent_to_switch[entity_id] = switch

    # pylint: disable=unused-argument
    def update_states(time, force_reload=False):
        """ Update states of all switches. """

        # First time this method gets called, force_reload should be True
        if force_reload or \
           datetime.now() - update_states.last_updated > \
           MIN_TIME_BETWEEN_SCANS:

            logger.info("Updating switch states")
            update_states.last_updated = datetime.now()

            for switch in switches:
                switch.update_ha_state(hass)

    update_states(None, True)

    def handle_switch_service(service):
        """ Handles calls to the switch services. """
        devices = [ent_to_switch[entity_id] for entity_id
                   in extract_entity_ids(hass, service)
                   if entity_id in ent_to_switch]

        if not devices:
            devices = switches

        for switch in devices:
            if service.service == SERVICE_TURN_ON:
                switch.turn_on()
            else:
                switch.turn_off()

            switch.update_ha_state(hass)

    # Track all switches in a group
    group.setup_group(hass, GROUP_NAME_ALL_SWITCHES,
                      ent_to_switch.keys(), False)

    # Update state every 30 seconds
    hass.track_time_change(update_states, second=[0, 30])

    hass.services.register(DOMAIN, SERVICE_TURN_OFF, handle_switch_service)

    hass.services.register(DOMAIN, SERVICE_TURN_ON, handle_switch_service)

    return True
