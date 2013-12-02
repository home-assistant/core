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
    STATE_CATEGORY_ALL_DEVICES, DEVICE_STATE_HOME, DEVICE_STATE_NOT_HOME,
    STATE_ATTRIBUTE_NEXT_SUN_SETTING)

LIGHT_TRANSITION_TIME = timedelta(minutes=15)

DOMAIN_DOWNLOADER = "downloader"
DOMAIN_BROWSER = "browser"
DOMAIN_CHROMECAST = "chromecast"
DOMAIN_KEYBOARD = "keyboard"
DOMAIN_LIGHT_CONTROL = "light_control"

SERVICE_DOWNLOAD_FILE = "download_file"
SERVICE_BROWSE_URL = "browse_url"
SERVICE_CHROMECAST_YOUTUBE_VIDEO = "play_youtube_video"
SERVICE_TURN_LIGHT_ON = "turn_light_on"
SERVICE_TURN_LIGHT_OFF = "turn_light_off"
SERVICE_KEYBOARD_VOLUME_UP = "volume_up"
SERVICE_KEYBOARD_VOLUME_DOWN = "volume_down"
SERVICE_KEYBOARD_VOLUME_MUTE = "volume_mute"
SERVICE_KEYBOARD_MEDIA_PLAY_PAUSE = "media_play_pause"
SERVICE_KEYBOARD_MEDIA_NEXT_TRACK = "media_next_track"
SERVICE_KEYBOARD_MEDIA_PREV_TRACK = "media_prev_track"


def _hue_process_transition_time(transition_seconds):
    """ Transition time is in 1/10th seconds
        and cannot exceed MAX_TRANSITION_TIME. """

    # Max transition time for Hue is 900 seconds/15 minutes
    return min(9000, transition_seconds * 10)


# pylint: disable=too-few-public-methods
class LightTrigger(object):
    """ Class to turn on lights based on state of devices and the sun
        or triggered by light events. """

    def __init__(self, bus, statemachine, device_tracker, light_control):
        self.bus = bus
        self.statemachine = statemachine
        self.light_control = light_control

        self.logger = logging.getLogger(__name__)

        # Track home coming of each seperate device
        for category in device_tracker.device_state_categories:
            ha.track_state_change(bus, category,
                                  DEVICE_STATE_NOT_HOME, DEVICE_STATE_HOME,
                                  self._handle_device_state_change)

        # Track when all devices are gone to shut down lights
        ha.track_state_change(bus, STATE_CATEGORY_ALL_DEVICES,
                              DEVICE_STATE_HOME, DEVICE_STATE_NOT_HOME,
                              self._handle_device_state_change)

        # Track every time sun rises so we can schedule a time-based
        # pre-sun set event
        ha.track_state_change(bus, STATE_CATEGORY_SUN,
                              SUN_STATE_BELOW_HORIZON, SUN_STATE_ABOVE_HORIZON,
                              self._handle_sun_rising)

        # If the sun is already above horizon
        # schedule the time-based pre-sun set event
        if statemachine.is_state(STATE_CATEGORY_SUN, SUN_STATE_ABOVE_HORIZON):
            self._handle_sun_rising(None, None, None)

    # pylint: disable=unused-argument
    def _handle_sun_rising(self, category, old_state, new_state):
        """The moment sun sets we want to have all the lights on.
           We will schedule to have each light start after one another
           and slowly transition in."""

        start_point = self._time_for_light_before_sun_set()

        def turn_on(light):
            """ Lambda can keep track of function parameters but not local
            parameters. If we put the lambda directly in the below statement
            only the last light would be turned on.. """
            return lambda now: self._turn_light_on_before_sunset(light)

        for index, light_id in enumerate(self.light_control.light_ids):
            ha.track_time_change(self.bus, turn_on(light_id),
                                 point_in_time=(start_point +
                                                index * LIGHT_TRANSITION_TIME))

    def _turn_light_on_before_sunset(self, light_id=None):
        """ Helper function to turn on lights slowly if there
            are devices home and the light is not on yet. """
        if self.statemachine.is_state(STATE_CATEGORY_ALL_DEVICES,
           DEVICE_STATE_HOME) and not self.light_control.is_light_on(light_id):

            self.light_control.turn_light_on(light_id,
                                             LIGHT_TRANSITION_TIME.seconds)

    def _handle_device_state_change(self, category, old_state, new_state):
        """ Function to handle tracked device state changes. """
        lights_are_on = self.light_control.is_light_on()

        light_needed = (not lights_are_on and
                        self.statemachine.is_state(STATE_CATEGORY_SUN,
                                                   SUN_STATE_BELOW_HORIZON))

        # Specific device came home ?
        if (category != STATE_CATEGORY_ALL_DEVICES and
           new_state['state'] == DEVICE_STATE_HOME):

            # These variables are needed for the elif check
            now = datetime.now()
            start_point = self._time_for_light_before_sun_set()

            # Do we need lights?
            if light_needed:

                self.logger.info(
                    "Home coming event for {}. Turning lights on".
                    format(category))

                self.light_control.turn_light_on()

            # Are we in the time span were we would turn on the lights
            # if someone would be home?
            # Check this by seeing if current time is later then the point
            # in time when we would start putting the lights on.
            elif start_point < now < self._next_sun_setting():

                # Check for every light if it would be on if someone was home
                # when the fading in started and turn it on if so
                for index, light_id in enumerate(self.light_control.light_ids):

                    if now > start_point + index * LIGHT_TRANSITION_TIME:
                        self.light_control.turn_light_on(light_id)

                    else:
                        # If this light didn't happen to be turned on yet so
                        # will all the following then, break.
                        break

        # Did all devices leave the house?
        elif (category == STATE_CATEGORY_ALL_DEVICES and
              new_state['state'] == DEVICE_STATE_NOT_HOME and lights_are_on):

            self.logger.info(("Everyone has left but lights are on. "
                              "Turning lights off"))
            self.light_control.turn_light_off()

    def _next_sun_setting(self):
        """ Returns the datetime object representing the next sun setting. """
        state = self.statemachine.get_state(STATE_CATEGORY_SUN)

        return ha.str_to_datetime(
            state['attributes'][STATE_ATTRIBUTE_NEXT_SUN_SETTING])

    def _time_for_light_before_sun_set(self):
        """ Helper method to calculate the point in time we have to start
        fading in lights so that all the lights are on the moment the sun
        sets.
        """

        return (self._next_sun_setting() -
                LIGHT_TRANSITION_TIME * len(self.light_control.light_ids))


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

        self.bridge = phue.Bridge(host)
        self.lights = self.bridge.get_light_objects()
        self.light_ids = [light.light_id for light in self.lights]

        self.success_init = True

    def is_light_on(self, light_id=None):
        """ Returns if specified or all light are on. """
        if not light_id:
            return sum([1 for light in self.lights if light.on]) > 0

        else:
            return self.bridge.get_light(light_id, 'on')

    def turn_light_on(self, light_id=None, transition_seconds=None):
        """ Turn the specified or all lights on. """
        if not light_id:
            light_id = self.light_ids

        command = {'on': True, 'xy': [0.5119, 0.4147], 'bri': 164}

        if transition_seconds:
            command['transitiontime'] = \
                _hue_process_transition_time(transition_seconds)

        self.bridge.set_light(light_id, command)

    def turn_light_off(self, light_id=None, transition_seconds=None):
        """ Turn the specified or all lights off. """
        if not light_id:
            light_id = self.light_ids

        command = {'on': False}

        if transition_seconds:
            command['transitiontime'] = \
                _hue_process_transition_time(transition_seconds)

        self.bridge.set_light(light_id, command)


def setup_light_control_services(bus, light_control):
    """ Exposes light control via services. """

    def handle_light_event(service):
        """ Hande a turn light on or off service call. """
        light_id = service.data.get("light_id", None)
        transition_seconds = service.data.get("transition_seconds", None)

        if service.service == SERVICE_TURN_LIGHT_ON:
            light_control.turn_light_on(light_id, transition_seconds)
        else:
            light_control.turn_light_off(light_id, transition_seconds)

    # Listen for light on and light off events
    bus.register_service(DOMAIN_LIGHT_CONTROL, SERVICE_TURN_LIGHT_ON,
                         handle_light_event)

    bus.register_service(DOMAIN_LIGHT_CONTROL, SERVICE_TURN_LIGHT_OFF,
                         handle_light_event)

    return True


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


def setup_chromecast(bus, host):
    """ Listen for chromecast events. """
    from homeassistant.packages import pychromecast

    bus.register_service(DOMAIN_CHROMECAST, "start_fireplace",
                         lambda event:
                         pychromecast.play_youtube_video(host, "eyU3bRy2x44"))

    bus.register_service(DOMAIN_CHROMECAST, "start_epic_sax",
                         lambda event:
                         pychromecast.play_youtube_video(host, "kxopViU98Xo"))

    bus.register_service(DOMAIN_CHROMECAST, SERVICE_CHROMECAST_YOUTUBE_VIDEO,
                         lambda event:
                         pychromecast.play_youtube_video(host,
                                                         event.data['video']))

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
