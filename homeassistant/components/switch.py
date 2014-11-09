"""
homeassistant.components.switch
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Component to interface with various switches that can be controlled remotely.
"""
import logging
from datetime import datetime, timedelta

import homeassistant as ha
import homeassistant.util as util
from homeassistant.components import (
    ToggleDevice, group, extract_entity_ids, STATE_ON,
    SERVICE_TURN_ON, SERVICE_TURN_OFF, ATTR_ENTITY_ID, ATTR_FRIENDLY_NAME)

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

    hass.call_service(DOMAIN, SERVICE_TURN_ON, data)


def turn_off(hass, entity_id=None):
    """ Turns all or specified switch off. """
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None

    hass.call_service(DOMAIN, SERVICE_TURN_OFF, data)


# pylint: disable=too-many-branches
def setup(hass, config):
    """ Track states and offer events for switches. """
    logger = logging.getLogger(__name__)

    if not util.validate_config(config, {DOMAIN: [ha.CONF_TYPE]}, logger):
        return False

    switch_type = config[DOMAIN][ha.CONF_TYPE]

    if switch_type == 'wemo':
        switch_init = get_wemo_switches

    else:
        logger.error("Unknown switch type specified: %s", switch_type)

        return False

    switches = switch_init(config[DOMAIN])

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

    # Track all wemos in a group
    group.setup_group(hass, GROUP_NAME_ALL_SWITCHES,
                      ent_to_switch.keys(), False)

    # Update state every 30 seconds
    hass.track_time_change(update_states, second=[0, 30])

    hass.services.register(DOMAIN, SERVICE_TURN_OFF, handle_switch_service)

    hass.services.register(DOMAIN, SERVICE_TURN_ON, handle_switch_service)

    return True


def get_wemo_switches(config):
    """ Find and return WeMo switches. """

    try:
        # Pylint does not play nice if not every folders has an __init__.py
        # pylint: disable=no-name-in-module, import-error
        import homeassistant.external.pywemo.pywemo as pywemo
    except ImportError:
        _LOGGER.exception((
            "Wemo:Failed to import pywemo. "
            "Did you maybe not run `git submodule init` "
            "and `git submodule update`?"))

        return []

    if ha.CONF_HOSTS in config:
        switches = (pywemo.device_from_host(host) for host
                    in config[ha.CONF_HOSTS].split(","))

    else:
        _LOGGER.info("Scanning for WeMo devices")
        switches = pywemo.discover_devices()

    # Filter out the switches and wrap in WemoSwitch object
    return [WemoSwitch(switch) for switch in switches
            if isinstance(switch, pywemo.Switch)]


class WemoSwitch(ToggleDevice):
    """ represents a WeMo switch within home assistant. """
    def __init__(self, wemo):
        self.wemo = wemo
        self.state_attr = {ATTR_FRIENDLY_NAME: wemo.name}

    def get_name(self):
        """ Returns the name of the switch if any. """
        return self.wemo.name

    def turn_on(self, **kwargs):
        """ Turns the switch on. """
        self.wemo.on()

    def turn_off(self):
        """ Turns the switch off. """
        self.wemo.off()

    def is_on(self):
        """ True if switch is on. """
        return self.wemo.get_state(True)

    def get_state_attributes(self):
        """ Returns optional state attributes. """
        return self.state_attr
