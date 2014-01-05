"""
homeassistant.components.light
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provides functionality to interact with lights.
"""

import logging
from datetime import datetime, timedelta

import homeassistant as ha
import homeassistant.util as util
import homeassistant.components.group as group

DOMAIN = "light"

STATE_GROUP_NAME_ALL_LIGHTS = 'all_lights'
STATE_CATEGORY_ALL_LIGHTS = group.STATE_CATEGORY_FORMAT.format(
    STATE_GROUP_NAME_ALL_LIGHTS)

STATE_CATEGORY_FORMAT = DOMAIN + ".{}"

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)


def is_on(statemachine, light_id=None):
    """ Returns if the lights are on based on the statemachine. """
    category = STATE_CATEGORY_FORMAT.format(light_id) if light_id \
        else STATE_CATEGORY_ALL_LIGHTS

    return statemachine.is_state(category, ha.STATE_ON)


def turn_on(bus, light_id=None, transition_seconds=None):
    """ Turns all or specified light on. """
    data = {}

    if light_id:
        data["light_id"] = light_id

    if transition_seconds:
        data["transition_seconds"] = transition_seconds

    bus.call_service(DOMAIN, ha.SERVICE_TURN_ON, data)


def turn_off(bus, light_id=None, transition_seconds=None):
    """ Turns all or specified light off. """
    data = {}

    if light_id:
        data["light_id"] = light_id

    if transition_seconds:
        data["transition_seconds"] = transition_seconds

    bus.call_service(DOMAIN, ha.SERVICE_TURN_OFF, data)


def setup(bus, statemachine, light_control):
    """ Exposes light control via statemachine and services. """

    logger = logging.getLogger(__name__)

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
                state_category = STATE_CATEGORY_FORMAT.format(light_id)

                new_state = ha.STATE_ON if state else ha.STATE_OFF

                statemachine.set_state(state_category, new_state)

    ha.track_time_change(bus, update_light_state, second=[0, 30])

    update_light_state(None)

    # Track the all lights state
    light_cats = [STATE_CATEGORY_FORMAT.format(light_id) for light_id
                  in light_control.light_ids]

    group.setup(bus, statemachine, STATE_GROUP_NAME_ALL_LIGHTS, light_cats)

    def handle_light_service(service):
        """ Hande a turn light on or off service call. """
        light_id = service.data.get("light_id", None)
        transition_seconds = service.data.get("transition_seconds", None)

        if service.service == ha.SERVICE_TURN_ON:
            light_control.turn_light_on(light_id, transition_seconds)
        else:
            light_control.turn_light_off(light_id, transition_seconds)

        update_light_state(None)

    # Listen for light on and light off events
    bus.register_service(DOMAIN, ha.SERVICE_TURN_ON,
                         handle_light_service)

    bus.register_service(DOMAIN, ha.SERVICE_TURN_OFF,
                         handle_light_service)

    return True


class HueLightControl(object):
    """ Class to interface with the Hue light system. """

    def __init__(self, host=None):
        try:
            import phue
        except ImportError:
            logging.getLogger(__name__).exception(
                "HueLightControl: Error while importing dependency phue.")

            self.success_init = False

            return

        self._bridge = phue.Bridge(host)

        self._light_map = {util.slugify(light.name): light for light
                           in self._bridge.get_light_objects()}

        self.success_init = True

    @property
    def light_ids(self):
        """ Return a list of light ids. """
        return self._light_map.keys()

    def is_light_on(self, light_id=None):
        """ Returns if specified or all light are on. """
        if not light_id:
            return any(
                [True for light in self._light_map.values() if light.on])

        else:
            return self._bridge.get_light(self._convert_id(light_id), 'on')

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
        else:
            light_id = [light.light_id for light in self._light_map.values()]

        command = {'on': True, 'xy': [0.5119, 0.4147], 'bri': 164} if turn \
            else {'on': False}

        if transition_seconds:
            # Transition time is in 1/10th seconds and cannot exceed
            # MAX_TRANSITION_TIME which is 900 seconds for Hue.
            command['transitiontime'] = min(9000, transition_seconds * 10)

        self._bridge.set_light(light_id, command)

    def _convert_id(self, light_id):
        """ Returns internal light id to be used with phue. """
        return self._light_map[light_id].light_id
