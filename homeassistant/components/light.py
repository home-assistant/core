"""
homeassistant.components.light
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provides functionality to interact with lights.
"""

import logging
import socket
from datetime import datetime, timedelta

import homeassistant as ha
import homeassistant.util as util
from homeassistant.components import (group, STATE_ON, STATE_OFF,
                                      SERVICE_TURN_ON, SERVICE_TURN_OFF,
                                      ATTR_ENTITY_ID)


DOMAIN = "light"

GROUP_NAME_ALL_LIGHTS = 'all_lights'
ENTITY_ID_ALL_LIGHTS = group.ENTITY_ID_FORMAT.format(
    GROUP_NAME_ALL_LIGHTS)

ENTITY_ID_FORMAT = DOMAIN + ".{}"

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)


def is_on(statemachine, entity_id=None):
    """ Returns if the lights are on based on the statemachine. """
    entity_id = entity_id or ENTITY_ID_ALL_LIGHTS

    return statemachine.is_state(entity_id, STATE_ON)


def turn_on(bus, entity_id=None, transition_seconds=None):
    """ Turns all or specified light on. """
    data = {}

    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    if transition_seconds:
        data["transition_seconds"] = transition_seconds

    bus.call_service(DOMAIN, SERVICE_TURN_ON, data)


def turn_off(bus, entity_id=None, transition_seconds=None):
    """ Turns all or specified light off. """
    data = {}

    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    if transition_seconds:
        data["transition_seconds"] = transition_seconds

    bus.call_service(DOMAIN, SERVICE_TURN_OFF, data)


def setup(bus, statemachine, light_control):
    """ Exposes light control via statemachine and services. """

    logger = logging.getLogger(__name__)

    ent_to_light = {}
    light_to_ent = {}

    def update_light_state(time):  # pylint: disable=unused-argument
        """ Track the state of the lights. """
        try:
            should_update = datetime.now() - update_light_state.last_updated \
                > MIN_TIME_BETWEEN_SCANS

        except AttributeError:  # if last_updated does not exist
            should_update = True

        if should_update:
            logger.info("Updating light status")
            update_light_state.last_updated = datetime.now()
            names = None

            states = light_control.get_states()

            for light_id, is_light_on in states.items():
                try:
                    entity_id = light_to_ent[light_id]
                except KeyError:
                    # We have not seen this light before, set it up

                    # Load light names if not loaded this update call
                    if names is None:
                        names = light_control.get_names()

                    name = names.get(
                        light_id, "Unknown Light {}".format(len(ent_to_light)))

                    logger.info("Found new light {}".format(name))

                    entity_id = ENTITY_ID_FORMAT.format(util.slugify(name))

                    ent_to_light[entity_id] = light_id
                    light_to_ent[light_id] = entity_id

                statemachine.set_state(entity_id,
                                       STATE_ON if is_light_on else STATE_OFF)

    # Update light state and discover lights for tracking the group
    update_light_state(None)

    # Track all lights in a group
    group.setup(bus, statemachine,
                GROUP_NAME_ALL_LIGHTS, light_to_ent.values())

    def handle_light_service(service):
        """ Hande a turn light on or off service call. """
        entity_id = service.data.get(ATTR_ENTITY_ID, None)
        transition_seconds = service.data.get("transition_seconds", None)

        if service.service == SERVICE_TURN_ON:
            light_control.turn_light_on(ent_to_light.get(entity_id),
                                        transition_seconds)
        else:
            light_control.turn_light_off(ent_to_light.get(entity_id),
                                         transition_seconds)

        update_light_state(None)

    # Update light state every 30 seconds
    ha.track_time_change(bus, update_light_state, second=[0, 30])

    # Listen for light on and light off service calls
    bus.register_service(DOMAIN, SERVICE_TURN_ON,
                         handle_light_service)

    bus.register_service(DOMAIN, SERVICE_TURN_OFF,
                         handle_light_service)

    return True


class HueLightControl(object):
    """ Class to interface with the Hue light system. """

    def __init__(self, host=None):
        logger = logging.getLogger(__name__)

        try:
            import phue
        except ImportError:
            logger.exception(
                "HueLightControl:Error while importing dependency phue.")

            self.success_init = False

            return

        try:
            self._bridge = phue.Bridge(host)
        except socket.error:  # Error connecting using Phue
            logger.exception((
                "HueLightControl:Error while connecting to the bridge. "
                "Is phue registered?"))

            self.success_init = False

            return

        if len(self._bridge.get_light()) == 0:
            logger.error("HueLightControl:Could not find any lights. ")

            self.success_init = False
        else:
            self.success_init = True

    def get_names(self):
        """ Return a dict with id mapped to name. """
        try:
            return {int(item[0]): item[1]['name'] for item
                    in self._bridge.get_light().items()}

        except (socket.error, KeyError):
            # socket.error because sometimes we cannot reach Hue
            # KeyError if we got unexpected data
            return {}

    def get_states(self):
        """ Return a dict with id mapped to boolean is_on. """

        try:
            # Light is on if reachable and on
            return {int(itm[0]):
                    itm[1]['state']['reachable'] and itm[1]['state']['on']
                    for itm in self._bridge.get_api()['lights'].items()}

        except (socket.error, KeyError):
            # socket.error because sometimes we cannot reach Hue
            # KeyError if we got unexpected data
            return {}

    def turn_light_on(self, light_id=None, transition_seconds=None):
        """ Turn the specified or all lights on. """
        self._turn_light(True, light_id, transition_seconds)

    def turn_light_off(self, light_id=None, transition_seconds=None):
        """ Turn the specified or all lights off. """
        self._turn_light(False, light_id, transition_seconds)

    def _turn_light(self, turn, light_id, transition_seconds):
        """ Helper method to turn lights on or off. """
        if turn:
            command = {'on': True, 'xy': [0.5119, 0.4147], 'bri': 164}
        else:
            command = {'on': False}

        if light_id is None:
            light_id = [light.light_id for light in self._bridge.lights]

        if transition_seconds is not None:
            # Transition time is in 1/10th seconds and cannot exceed
            # 900 seconds.
            command['transitiontime'] = min(9000, transition_seconds * 10)

        self._bridge.set_light(light_id, command)
