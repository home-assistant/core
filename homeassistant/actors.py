"""
homeassistant.actors
~~~~~~~~~~~~~~~~~~~~

This module provides actors that will react to events happening within
homeassistant or provide services.

"""

import os
import logging
from datetime import datetime, timedelta
import re

import requests

import homeassistant as ha
import homeassistant.util as util
from homeassistant.observers import (
    STATE_CATEGORY_SUN, SUN_STATE_BELOW_HORIZON, SUN_STATE_ABOVE_HORIZON,
    is_sun_up, next_sun_setting,

    STATE_CATEGORY_ALL_DEVICES, DEVICE_STATE_HOME, DEVICE_STATE_NOT_HOME,
    STATE_CATEGORY_DEVICE_FORMAT, get_device_ids, is_device_home,

    is_light_on, turn_light_on, turn_light_off, get_light_ids)

LIGHT_TRANSITION_TIME = timedelta(minutes=15)

DOMAIN_DOWNLOADER = "downloader"
DOMAIN_BROWSER = "browser"
DOMAIN_KEYBOARD = "keyboard"

SERVICE_DOWNLOAD_FILE = "download_file"
SERVICE_BROWSE_URL = "browse_url"
SERVICE_KEYBOARD_VOLUME_UP = "volume_up"
SERVICE_KEYBOARD_VOLUME_DOWN = "volume_down"
SERVICE_KEYBOARD_VOLUME_MUTE = "volume_mute"
SERVICE_KEYBOARD_MEDIA_PLAY_PAUSE = "media_play_pause"
SERVICE_KEYBOARD_MEDIA_NEXT_TRACK = "media_next_track"
SERVICE_KEYBOARD_MEDIA_PREV_TRACK = "media_prev_track"


# pylint: disable=too-many-branches
def setup_device_light_triggers(bus, statemachine):
    """ Triggers to turn lights on or off based on device precense. """

    logger = logging.getLogger(__name__)

    device_state_categories = [STATE_CATEGORY_DEVICE_FORMAT.format(device_id)
                               for device_id in get_device_ids(statemachine)]

    if len(device_state_categories) == 0:
        logger.error("LightTrigger:No devices given to track")

        return False

    light_ids = get_light_ids(statemachine)

    if len(light_ids) == 0:
        logger.error("LightTrigger:No lights found to turn on")

        return False

    # Calculates the time when to start fading lights in when sun sets
    time_for_light_before_sun_set = lambda: \
        (next_sun_setting(statemachine) - LIGHT_TRANSITION_TIME *
         len(light_ids))

    # pylint: disable=unused-argument
    def handle_sun_rising(category, old_state, new_state):
        """The moment sun sets we want to have all the lights on.
           We will schedule to have each light start after one another
           and slowly transition in."""

        def turn_light_on_before_sunset(light_id):
            """ Helper function to turn on lights slowly if there
                are devices home and the light is not on yet. """
            if (is_device_home(statemachine) and
               not is_light_on(statemachine, light_id)):

                turn_light_on(bus, light_id, LIGHT_TRANSITION_TIME.seconds)

        def turn_on(light_id):
            """ Lambda can keep track of function parameters but not local
            parameters. If we put the lambda directly in the below statement
            only the last light will be turned on.. """
            return lambda now: turn_light_on_before_sunset(light_id)

        start_point = time_for_light_before_sun_set()

        for index, light_id in enumerate(light_ids):
            ha.track_time_change(bus, turn_on(light_id),
                                 point_in_time=(start_point +
                                                index * LIGHT_TRANSITION_TIME))

    # Track every time sun rises so we can schedule a time-based
    # pre-sun set event
    ha.track_state_change(bus, STATE_CATEGORY_SUN, SUN_STATE_BELOW_HORIZON,
                          SUN_STATE_ABOVE_HORIZON, handle_sun_rising)

    # If the sun is already above horizon
    # schedule the time-based pre-sun set event
    if is_sun_up(statemachine):
        handle_sun_rising(None, None, None)

    def handle_device_state_change(category, old_state, new_state):
        """ Function to handle tracked device state changes. """
        lights_are_on = is_light_on(statemachine)

        light_needed = not (lights_are_on or is_sun_up(statemachine))

        # Specific device came home ?
        if (category != STATE_CATEGORY_ALL_DEVICES and
           new_state['state'] == DEVICE_STATE_HOME):

            # These variables are needed for the elif check
            now = datetime.now()
            start_point = time_for_light_before_sun_set()

            # Do we need lights?
            if light_needed:

                logger.info(
                    "Home coming event for {}. Turning lights on".
                    format(category))

                turn_light_on(bus)

            # Are we in the time span were we would turn on the lights
            # if someone would be home?
            # Check this by seeing if current time is later then the point
            # in time when we would start putting the lights on.
            elif start_point < now < next_sun_setting(statemachine):

                # Check for every light if it would be on if someone was home
                # when the fading in started and turn it on if so
                for index, light_id in enumerate(light_ids):

                    if now > start_point + index * LIGHT_TRANSITION_TIME:
                        turn_light_on(bus, light_id)

                    else:
                        # If this light didn't happen to be turned on yet so
                        # will all the following then, break.
                        break

        # Did all devices leave the house?
        elif (category == STATE_CATEGORY_ALL_DEVICES and
              new_state['state'] == DEVICE_STATE_NOT_HOME and lights_are_on):

            logger.info(
                "Everyone has left but lights are on. Turning lights off")

            turn_light_off(bus)

    # Track home coming of each seperate device
    for category in device_state_categories:
        ha.track_state_change(bus, category,
                              DEVICE_STATE_NOT_HOME, DEVICE_STATE_HOME,
                              handle_device_state_change)

    # Track when all devices are gone to shut down lights
    ha.track_state_change(bus, STATE_CATEGORY_ALL_DEVICES,
                          DEVICE_STATE_HOME, DEVICE_STATE_NOT_HOME,
                          handle_device_state_change)

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
            return sum(
                [1 for light in self._light_map.values() if light.on]) > 0

        else:
            return self._bridge.get_light(self._convert_id(light_id), 'on')

    def turn_light_on(self, light_id=None, transition_seconds=None):
        """ Turn the specified or all lights on. """
        self._turn_light(True, light_id, transition_seconds)

    def turn_light_off(self, light_id=None, transition_seconds=None):
        """ Turn the specified or all lights off. """
        self._turn_light(False, light_id, transition_seconds)

    def _turn_light(self, turn_on, light_id=None, transition_seconds=None):
        """ Helper method to turn lights on or off. """
        if light_id:
            light_id = self._convert_id(light_id)
        else:
            light_id = [light.light_id for light in self._light_map.values()]

        command = {'on': True, 'xy': [0.5119, 0.4147], 'bri': 164} if turn_on \
            else {'on': False}

        if transition_seconds:
            # Transition time is in 1/10th seconds and cannot exceed
            # MAX_TRANSITION_TIME which is 900 seconds for Hue.
            command['transitiontime'] = min(9000, transition_seconds * 10)

        self._bridge.set_light(light_id, command)

    def _convert_id(self, light_id):
        """ Returns internal light id to be used with phue. """
        return self._light_map[light_id].light_id


def setup_file_downloader(bus, download_path):
    """ Listens for download events to download files. """

    logger = logging.getLogger(__name__)

    if not os.path.isdir(download_path):

        logger.error(
            ("FileDownloader:"
             "Download path {} does not exist. File Downloader not active.").
            format(download_path))

        return False

    def download_file(service):
        """ Downloads file specified in the url. """

        try:
            req = requests.get(service.data['url'], stream=True)
            if req.status_code == 200:
                filename = None

                if 'content-disposition' in req.headers:
                    match = re.findall(r"filename=(\S+)",
                                       req.headers['content-disposition'])

                    if len(match) > 0:
                        filename = match[0].strip("'\" ")

                if not filename:
                    filename = os.path.basename(service.data['url']).strip()

                if not filename:
                    filename = "ha_download"

                # Remove stuff to ruin paths
                filename = util.sanitize_filename(filename)

                path, ext = os.path.splitext(os.path.join(download_path,
                                                          filename))

                # If file exist append a number. We test filename, filename_2..
                tries = 0
                while True:
                    tries += 1

                    name_suffix = "" if tries == 1 else "_{}".format(tries)
                    final_path = path + name_suffix + ext

                    if not os.path.isfile(final_path):
                        break

                logger.info("FileDownloader:{} -> {}".format(
                            service.data['url'], final_path))

                with open(final_path, 'wb') as fil:
                    for chunk in req.iter_content(1024):
                        fil.write(chunk)

        except requests.exceptions.ConnectionError:
            logger.exception("FileDownloader:ConnectionError occured for {}".
                             format(service.data['url']))

    bus.register_service(DOMAIN_DOWNLOADER, SERVICE_DOWNLOAD_FILE,
                         download_file)

    return True


def setup_webbrowser(bus):
    """ Listen for browse_url events and open
        the url in the default webbrowser. """

    import webbrowser

    bus.register_service(DOMAIN_BROWSER, SERVICE_BROWSE_URL,
                         lambda event: webbrowser.open(event.data['url']))

    return True


def setup_media_buttons(bus):
    """ Listen for keyboard events. """
    try:
        import pykeyboard
    except ImportError:
        logging.getLogger(__name__).exception(
            "MediaButtons: Error while importing dependency PyUserInput.")

        return False

    keyboard = pykeyboard.PyKeyboard()
    keyboard.special_key_assignment()

    bus.register_service(DOMAIN_KEYBOARD, SERVICE_KEYBOARD_VOLUME_UP,
                         lambda event:
                         keyboard.tap_key(keyboard.volume_up_key))

    bus.register_service(DOMAIN_KEYBOARD, SERVICE_KEYBOARD_VOLUME_DOWN,
                         lambda event:
                         keyboard.tap_key(keyboard.volume_down_key))

    bus.register_service(DOMAIN_KEYBOARD, SERVICE_KEYBOARD_VOLUME_MUTE,
                         lambda event:
                         keyboard.tap_key(keyboard.volume_mute_key))

    bus.register_service(DOMAIN_KEYBOARD, SERVICE_KEYBOARD_MEDIA_PLAY_PAUSE,
                         lambda event:
                         keyboard.tap_key(keyboard.media_play_pause_key))

    bus.register_service(DOMAIN_KEYBOARD, SERVICE_KEYBOARD_MEDIA_NEXT_TRACK,
                         lambda event:
                         keyboard.tap_key(keyboard.media_next_track_key))

    bus.register_service(DOMAIN_KEYBOARD, SERVICE_KEYBOARD_MEDIA_PREV_TRACK,
                         lambda event:
                         keyboard.tap_key(keyboard.media_prev_track_key))

    return True
