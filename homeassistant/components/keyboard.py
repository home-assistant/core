"""
homeassistant.components.keyboard
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provides functionality to emulate keyboard presses on host machine.
"""
import logging

import homeassistant.components as components

DOMAIN = "keyboard"


def volume_up(bus):
    """ Press the keyboard button for volume up. """
    bus.call_service(DOMAIN, components.SERVICE_VOLUME_UP)


def volume_down(bus):
    """ Press the keyboard button for volume down. """
    bus.call_service(DOMAIN, components.SERVICE_VOLUME_DOWN)


def volume_mute(bus):
    """ Press the keyboard button for muting volume. """
    bus.call_service(DOMAIN, components.SERVICE_VOLUME_MUTE)


def media_play_pause(bus):
    """ Press the keyboard button for play/pause. """
    bus.call_service(DOMAIN, components.SERVICE_MEDIA_PLAY_PAUSE)


def media_next_track(bus):
    """ Press the keyboard button for next track. """
    bus.call_service(DOMAIN, components.SERVICE_MEDIA_NEXT_TRACK)


def media_prev_track(bus):
    """ Press the keyboard button for prev track. """
    bus.call_service(DOMAIN, components.SERVICE_MEDIA_PREV_TRACK)


def setup(bus):
    """ Listen for keyboard events. """
    try:
        import pykeyboard
    except ImportError:
        logging.getLogger(__name__).exception(
            "MediaButtons: Error while importing dependency PyUserInput.")

        return False

    keyboard = pykeyboard.PyKeyboard()
    keyboard.special_key_assignment()

    bus.register_service(DOMAIN, components.SERVICE_VOLUME_UP,
                         lambda service:
                         keyboard.tap_key(keyboard.volume_up_key))

    bus.register_service(DOMAIN, components.SERVICE_VOLUME_DOWN,
                         lambda service:
                         keyboard.tap_key(keyboard.volume_down_key))

    bus.register_service(DOMAIN, components.SERVICE_VOLUME_MUTE,
                         lambda service:
                         keyboard.tap_key(keyboard.volume_mute_key))

    bus.register_service(DOMAIN, components.SERVICE_MEDIA_PLAY_PAUSE,
                         lambda service:
                         keyboard.tap_key(keyboard.media_play_pause_key))

    bus.register_service(DOMAIN, components.SERVICE_MEDIA_NEXT_TRACK,
                         lambda service:
                         keyboard.tap_key(keyboard.media_next_track_key))

    bus.register_service(DOMAIN, components.SERVICE_MEDIA_PREV_TRACK,
                         lambda service:
                         keyboard.tap_key(keyboard.media_prev_track_key))

    return True
