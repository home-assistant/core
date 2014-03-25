"""
Component to interface with WeMo devices on the network.
"""
import logging
import socket
from datetime import datetime, timedelta

import homeassistant as ha
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


# pylint: disable=too-many-branches
def setup(bus, statemachine):
    """ Track states and offer events for WeMo switches. """
    logger = logging.getLogger(__name__)

    try:
        import ouimeaux.environment as wemo_env
        import ouimeaux.device.switch as wemo_switch
        import ouimeaux.device.insight as wemo_insight
    except ImportError:
        logger.exception(("Failed to import ouimeaux. "
                          "Did you maybe not install the 'ouimeaux' "
                          "dependency?"))

        return False

    env = wemo_env.Environment()

    try:
        env.start()
    except socket.error:
        # If the socket is already in use
        logger.exception("Error starting WeMo environment")
        return False

    env.discover(5)

    if len(env.list_switches()) == 0:
        logger.error("No WeMo switches found")
        return False

    # Dict mapping serial no to entity IDs
    sno_to_ent = {}
    # Dict mapping entity IDs to devices
    ent_to_dev = {}

    def _update_wemo_state(device):
        """ Update the state of specified WeMo device. """

        # We currently only support switches
        if not isinstance(device, wemo_switch.Switch):
            return

        try:
            entity_id = sno_to_ent[device.serialnumber]

        except KeyError:
            # New device, set it up
            entity_id = util.ensure_unique_string(
                ENTITY_ID_FORMAT.format(util.slugify(device.name)),
                ent_to_dev.keys())

            sno_to_ent[device.serialnumber] = entity_id
            ent_to_dev[entity_id] = device

        state = STATE_ON if device.get_state(True) else STATE_OFF

        state_attr = {ATTR_FRIENDLY_NAME: device.name}

        if isinstance(device, wemo_insight.Insight):
            pass
            # Should work but doesn't..
            #state_attr[ATTR_TODAY_KWH] = device.today_kwh
            #state_attr[ATTR_CURRENT_POWER] = device.current_power
            #state_attr[ATTR_TODAY_ON_TIME] = device.today_on_time
            #state_attr[ATTR_TODAY_STANDBY_TIME] = device.today_standby_time

        statemachine.set_state(entity_id, state, state_attr)

    # pylint: disable=unused-argument
    def _update_wemos_state(time, force_reload=False):
        """ Update states of all WeMo devices. """

        # First time this method gets called, force_reload should be True
        if (force_reload or
           datetime.now() - _update_wemos_state.last_updated >
           MIN_TIME_BETWEEN_SCANS):

            logger.info("Updating WeMo status")
            _update_wemos_state.last_updated = datetime.now()

            for device in env:
                _update_wemo_state(device)

    _update_wemos_state(None, True)

    # Track all lights in a group
    group.setup(bus, statemachine,
                GROUP_NAME_ALL_WEMOS, sno_to_ent.values())

    def _handle_wemo_service(service):
        """ Handles calls to the WeMo service. """
        devices = [ent_to_dev[entity_id] for entity_id
                   in extract_entity_ids(statemachine, service)
                   if entity_id in ent_to_dev]

        if not devices:
            devices = ent_to_dev.values()

        for device in devices:
            if service.service == SERVICE_TURN_ON:
                device.on()
            else:
                device.off()

            _update_wemo_state(device)

    # Update WeMo state every 30 seconds
    ha.track_time_change(bus, _update_wemos_state, second=[0, 30])

    bus.register_service(DOMAIN, SERVICE_TURN_OFF, _handle_wemo_service)

    bus.register_service(DOMAIN, SERVICE_TURN_ON, _handle_wemo_service)

    return True
