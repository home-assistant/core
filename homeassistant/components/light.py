"""
homeassistant.components.light
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provides functionality to interact with lights.
"""

import logging
from datetime import datetime, timedelta

import homeassistant as ha
import homeassistant.util as util
from homeassistant.components import general, group

DOMAIN = "light"

GROUP_NAME_ALL_LIGHTS = 'all_lights'
ENTITY_ID_ALL_LIGHTS = group.ENTITY_ID_FORMAT.format(
    GROUP_NAME_ALL_LIGHTS)

ENTITY_ID_FORMAT = DOMAIN + ".{}"

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)


def is_on(statemachine, entity_id=None):
    """ Returns if the lights are on based on the statemachine. """
    entity_id = entity_id or ENTITY_ID_ALL_LIGHTS

    return statemachine.is_state(entity_id, general.STATE_ON)


# pylint: disable=unused-argument
def turn_on(bus, entity_id=None, transition_seconds=None):
    """ Turns all or specified light on. """
    data = {}

    if entity_id:
        data[general.ATTR_ENTITY_ID] = entity_id

    if transition_seconds:
        data["transition_seconds"] = transition_seconds

    bus.call_service(DOMAIN, general.SERVICE_TURN_ON, data)


# pylint: disable=unused-argument
def turn_off(bus, entity_id=None, transition_seconds=None):
    """ Turns all or specified light off. """
    data = {}

    if entity_id:
        data[general.ATTR_ENTITY_ID] = entity_id

    if transition_seconds:
        data["transition_seconds"] = transition_seconds

    bus.call_service(DOMAIN, general.SERVICE_TURN_OFF, data)


def setup(bus, statemachine, light_control):
    """ Exposes light control via statemachine and services. """

    logger = logging.getLogger(__name__)

    entity_ids = {light_id: ENTITY_ID_FORMAT.format(light_id) for light_id
                  in light_control.light_ids}

    if not entity_ids:
        logger.error("Light:Found no lights to track")
        return

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

            status = {light_id: light_control.is_light_on(light_id)
                      for light_id in light_control.light_ids}

            for light_id, state in status.items():
                new_state = general.STATE_ON if state else general.STATE_OFF

                statemachine.set_state(entity_ids[light_id], new_state)

    ha.track_time_change(bus, update_light_state, second=[0, 30])

    update_light_state(None)

    # Track the all lights state
    group.setup(bus, statemachine, GROUP_NAME_ALL_LIGHTS, entity_ids.values())

    def handle_light_service(service):
        """ Hande a turn light on or off service call. """
        entity_id = service.data.get(general.ATTR_ENTITY_ID, None)
        transition_seconds = service.data.get("transition_seconds", None)

        object_id = util.split_entity_id(entity_id)[1] if entity_id else None

        if service.service == general.SERVICE_TURN_ON:
            light_control.turn_light_on(object_id, transition_seconds)
        else:
            light_control.turn_light_off(object_id, transition_seconds)

        update_light_state(None)

    # Listen for light on and light off events
    bus.register_service(DOMAIN, general.SERVICE_TURN_ON,
                         handle_light_service)

    bus.register_service(DOMAIN, general.SERVICE_TURN_OFF,
                         handle_light_service)

    return True


class HueLightControl(object):
    """ Class to interface with the Hue light system. """

    def __init__(self, host=None):
        logger = logging.getLogger(__name__)

        try:
            import phue
            import socket
        except ImportError:
            logger.exception(
                "HueLightControl:Error while importing dependency phue.")

            self.success_init = False
            self._light_map = {}

            return

        try:
            self._bridge = phue.Bridge(host)
        except socket.error:  # Error connecting using Phue
            logger.exception((
                "HueLightControl:Error while connecting to the bridge. "
                "Is phue registered?"))

            self.success_init = False
            self._light_map = {}

            return

        self._light_map = {util.slugify(light.name): light for light
                           in self._bridge.get_light_objects()}

        if not self._light_map:
            logger.error("HueLightControl:Could not find any lights. ")

            self.success_init = False
        else:
            self.success_init = True

    @property
    def light_ids(self):
        """ Return a list of light ids. """
        return self._light_map.keys()

    def is_light_on(self, light_id=None):
        """ Returns if specified or all light are on. """
        if not light_id:
            return any(
                True for light_id in self._light_map.keys()
                if self.is_light_on(light_id))

        else:
            light_id = self._convert_id(light_id)

            if not light_id:  # Not valid light_id submitted
                return False

            state = self._bridge.get_light(light_id)

            try:
                return state['state']['reachable'] and state['state']['on']
            except KeyError:
                # If key 'state', 'reachable' or 'on' not exists.
                return False

    def turn_light_on(self, light_id=None, transition_seconds=None):
        """ Turn the specified or all lights on. """
        self._turn_light(True, light_id, transition_seconds)

    def turn_light_off(self, light_id=None, transition_seconds=None):
        """ Turn the specified or all lights off. """
        self._turn_light(False, light_id, transition_seconds)

    def _turn_light(self, turn, light_id=None, transition_seconds=None):
        """ Helper method to turn lights on or off. """
        if light_id:
            light_id = self._convert_id(light_id)

            if not light_id:  # Not valid light id submitted
                return

        else:
            light_id = [light.light_id for light in self._light_map.values()]

        command = {'on': True, 'xy': [0.5119, 0.4147], 'bri': 164} if turn \
            else {'on': False}

        if transition_seconds:
            # Transition time is in 1/10th seconds and cannot exceed
            # 900 seconds.
            command['transitiontime'] = min(9000, transition_seconds * 10)

        self._bridge.set_light(light_id, command)

    def _convert_id(self, light_id):
        """ Returns internal light id to be used with phue. """
        try:
            return self._light_map[light_id].light_id
        except KeyError:  # if light_id is not a valid key
            return None
