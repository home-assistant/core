""" Support for Hue lights. """
import logging
import socket
from datetime import datetime, timedelta

import homeassistant as ha
from homeassistant.components import ToggleDevice, ATTR_FRIENDLY_NAME
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_XY_COLOR, ATTR_TRANSITION)

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

PHUE_CONFIG_FILE = "phue.conf"


def get_lights(hass, config):
    """ Gets the Hue lights. """
    logger = logging.getLogger(__name__)
    try:
        import phue
    except ImportError:
        logger.exception("Error while importing dependency phue.")

        return []

    host = config.get(ha.CONF_HOST, None)

    try:
        bridge = phue.Bridge(
            host, config_file_path=hass.get_config_path(PHUE_CONFIG_FILE))
    except socket.error:  # Error connecting using Phue
        logger.exception((
            "Error while connecting to the bridge. "
            "Did you follow the instructions to set it up?"))

        return []

    lights = {}

    def update_lights(force_reload=False):
        """ Updates the light states. """
        now = datetime.now()

        try:
            time_scans = now - update_lights.last_updated

            # force_reload == True, return if updated in last second
            # force_reload == False, return if last update was less then
            # MIN_TIME_BETWEEN_SCANS ago
            if force_reload and time_scans.seconds < 1 or \
               not force_reload and time_scans < MIN_TIME_BETWEEN_SCANS:
                return
        except AttributeError:
            # First time we run last_updated is not set, continue as usual
            pass

        update_lights.last_updated = now

        try:
            api = bridge.get_api()
        except socket.error:
            # socket.error when we cannot reach Hue
            logger.exception("Cannot reach the bridge")
            return

        api_states = api.get('lights')

        if not isinstance(api_states, dict):
            logger.error("Got unexpected result from Hue API")
            return

        for light_id, info in api_states.items():
            if light_id not in lights:
                lights[light_id] = HueLight(int(light_id), info,
                                            bridge, update_lights)
            else:
                lights[light_id].info = info

    update_lights()

    return list(lights.values())


class HueLight(ToggleDevice):
    """ Represents a Hue light """

    def __init__(self, light_id, info, bridge, update_lights):
        self.light_id = light_id
        self.info = info
        self.bridge = bridge
        self.update_lights = update_lights

    def get_name(self):
        """ Get the mame of the Hue light. """
        return self.info['name']

    def turn_on(self, **kwargs):
        """ Turn the specified or all lights on. """
        command = {'on': True}

        if ATTR_TRANSITION in kwargs:
            # Transition time is in 1/10th seconds and cannot exceed
            # 900 seconds.
            command['transitiontime'] = min(9000, kwargs[ATTR_TRANSITION] * 10)

        if ATTR_BRIGHTNESS in kwargs:
            command['bri'] = kwargs[ATTR_BRIGHTNESS]

        if ATTR_XY_COLOR in kwargs:
            command['xy'] = kwargs[ATTR_XY_COLOR]

        self.bridge.set_light(self.light_id, command)

    def turn_off(self, **kwargs):
        """ Turn the specified or all lights off. """
        command = {'on': False}

        if ATTR_TRANSITION in kwargs:
            # Transition time is in 1/10th seconds and cannot exceed
            # 900 seconds.
            command['transitiontime'] = min(9000, kwargs[ATTR_TRANSITION] * 10)

        self.bridge.set_light(self.light_id, command)

    def is_on(self):
        """ True if device is on. """
        self.update_lights()

        return self.info['state']['reachable'] and self.info['state']['on']

    def get_state_attributes(self):
        """ Returns optional state attributes. """
        attr = {
            ATTR_FRIENDLY_NAME: self.get_name()
        }

        if self.is_on():
            attr[ATTR_BRIGHTNESS] = self.info['state']['bri']
            attr[ATTR_XY_COLOR] = self.info['state']['xy']

        return attr

    def update(self):
        """ Synchronize state with bridge. """
        self.update_lights(True)
