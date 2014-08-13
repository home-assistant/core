"""
homeassistant.components.keyboard
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provides functionality to emulate keyboard presses on host machine.
"""
import logging

import homeassistant.components as components

DOMAIN = "keyboard"
DEPENDENCIES = []


def volume_up(hass):
    """ Press the keyboard button for volume up. """
    hass.call_service(DOMAIN, components.SERVICE_VOLUME_UP)


def volume_down(hass):
    """ Press the keyboard button for volume down. """
    hass.call_service(DOMAIN, components.SERVICE_VOLUME_DOWN)


def volume_mute(hass):
    """ Press the keyboard button for muting volume. """
    hass.call_service(DOMAIN, components.SERVICE_VOLUME_MUTE)


def media_play_pause(hass):
    """ Press the keyboard button for play/pause. """
    hass.call_service(DOMAIN, components.SERVICE_MEDIA_PLAY_PAUSE)


def media_next_track(hass):
    """ Press the keyboard button for next track. """
    hass.call_service(DOMAIN, components.SERVICE_MEDIA_NEXT_TRACK)


def media_prev_track(hass):
    """ Press the keyboard button for prev track. """
    hass.call_service(DOMAIN, components.SERVICE_MEDIA_PREV_TRACK)


# pylint: disable=unused-argument
def setup(hass, config):
    """ Listen for keyboard events. """
    try:
        import pykeyboard
    except ImportError:
        logging.getLogger(__name__).exception(
            "Error while importing dependency PyUserInput.")

        return False

    keyboard = pykeyboard.PyKeyboard()
    keyboard.special_key_assignment()

    hass.services.register(DOMAIN, components.SERVICE_VOLUME_UP,
                           lambda service:
                           keyboard.tap_key(keyboard.volume_up_key))

    hass.services.register(DOMAIN, components.SERVICE_VOLUME_DOWN,
                           lambda service:
                           keyboard.tap_key(keyboard.volume_down_key))

    hass.services.register(DOMAIN, components.SERVICE_VOLUME_MUTE,
                           lambda service:
                           keyboard.tap_key(keyboard.volume_mute_key))

    hass.services.register(DOMAIN, components.SERVICE_MEDIA_PLAY_PAUSE,
                           lambda service:
                           keyboard.tap_key(keyboard.media_play_pause_key))

    hass.services.register(DOMAIN, components.SERVICE_MEDIA_NEXT_TRACK,
                           lambda service:
                           keyboard.tap_key(keyboard.media_next_track_key))

    hass.services.register(DOMAIN, components.SERVICE_MEDIA_PREV_TRACK,
                           lambda service:
                           keyboard.tap_key(keyboard.media_prev_track_key))

    return True
