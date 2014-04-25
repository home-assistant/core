"""
Component to interface with WeMo devices on the network.
"""
import logging
from datetime import datetime, timedelta

import homeassistant.util as util
from homeassistant.components import (group, extract_entity_ids,
                                      STATE_ON, STATE_OFF,
                                      SERVICE_TURN_ON, SERVICE_TURN_OFF,
                                      ATTR_ENTITY_ID, ATTR_FRIENDLY_NAME)
DOMAIN = 'wemo'

GROUP_NAME_ALL_WEMOS = 'all_wemos'
ENTITY_ID_ALL_WEMOS = group.ENTITY_ID_FORMAT.format(
    GROUP_NAME_ALL_WEMOS)

ENTITY_ID_FORMAT = DOMAIN + '.{}'

ATTR_TODAY_KWH = "today_kwh"
ATTR_CURRENT_POWER = "current_power"
ATTR_TODAY_ON_TIME = "today_on_time"
ATTR_TODAY_STANDBY_TIME = "today_standby_time"

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)


def is_on(hass, entity_id=None):
    """ Returns if the wemo is on based on the statemachine. """
    entity_id = entity_id or ENTITY_ID_ALL_WEMOS

    return hass.states.is_state(entity_id, STATE_ON)


def turn_on(hass, entity_id=None):
    """ Turns all or specified wemo on. """
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None

    hass.call_service(DOMAIN, SERVICE_TURN_ON, data)


def turn_off(hass, entity_id=None):
    """ Turns all or specified wemo off. """
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None

    hass.call_service(DOMAIN, SERVICE_TURN_OFF, data)


# pylint: disable=too-many-branches
def setup(hass, hosts=None):
    """ Track states and offer events for WeMo switches. """
    logger = logging.getLogger(__name__)

    try:
        import homeassistant.external.pywemo.pywemo as pywemo
    except ImportError:
        logger.exception((
            "Failed to import pywemo. "
            "Did you maybe not run `git submodule init` "
            "and `git submodule update`?"))

        return False

    if hosts:
        devices = []

        for host in hosts:
            device = pywemo.device_from_host(host)

            if device:
                devices.append(device)

    else:
        logger.info("Scanning for WeMo devices")
        devices = pywemo.discover_devices()

    is_switch = lambda switch: isinstance(switch, pywemo.Switch)

    switches = [device for device in devices if is_switch(device)]

    if len(switches) == 0:
        logger.error("No WeMo switches found")
        return False

    # Dict mapping serial no to entity IDs
    sno_to_ent = {}
    # Dict mapping entity IDs to devices
    ent_to_dev = {}

    def update_wemo_state(device):
        """ Update the state of specified WeMo device. """

        # We currently only support switches
        if not is_switch(device):
            return

        try:
            entity_id = sno_to_ent[device.serialnumber]

        except KeyError:
            # New device, set it up
            entity_id = util.ensure_unique_string(
                ENTITY_ID_FORMAT.format(util.slugify(device.name)),
                list(ent_to_dev.keys()))

            sno_to_ent[device.serialnumber] = entity_id
            ent_to_dev[entity_id] = device

        state = STATE_ON if device.get_state(True) else STATE_OFF

        state_attr = {ATTR_FRIENDLY_NAME: device.name}

        if isinstance(device, pywemo.Insight):
            pass
            # Should work but doesn't..
            #state_attr[ATTR_TODAY_KWH] = device.today_kwh
            #state_attr[ATTR_CURRENT_POWER] = device.current_power
            #state_attr[ATTR_TODAY_ON_TIME] = device.today_on_time
            #state_attr[ATTR_TODAY_STANDBY_TIME] = device.today_standby_time

        hass.states.set(entity_id, state, state_attr)

    # pylint: disable=unused-argument
    def update_wemos_state(time, force_reload=False):
        """ Update states of all WeMo devices. """

        # First time this method gets called, force_reload should be True
        if (force_reload or
           datetime.now() - update_wemos_state.last_updated >
           MIN_TIME_BETWEEN_SCANS):

            logger.info("Updating WeMo status")
            update_wemos_state.last_updated = datetime.now()

            for device in switches:
                update_wemo_state(device)

    update_wemos_state(None, True)

    # Track all lights in a group
    group.setup(hass, GROUP_NAME_ALL_WEMOS, sno_to_ent.values())

    def handle_wemo_service(service):
        """ Handles calls to the WeMo service. """
        devices = [ent_to_dev[entity_id] for entity_id
                   in extract_entity_ids(hass, service)
                   if entity_id in ent_to_dev]

        if not devices:
            devices = ent_to_dev.values()

        for device in devices:
            if service.service == SERVICE_TURN_ON:
                device.on()
            else:
                device.off()

            update_wemo_state(device)

    # Update WeMo state every 30 seconds
    hass.track_time_change(update_wemos_state, second=[0, 30])

    hass.services.register(DOMAIN, SERVICE_TURN_OFF, handle_wemo_service)

    hass.services.register(DOMAIN, SERVICE_TURN_ON, handle_wemo_service)

    return True
