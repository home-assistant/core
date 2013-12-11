"""
homeassistant.components.keyboard
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provides functionality to emulate keyboard presses on host machine.
"""
import logging

DOMAIN_KEYBOARD = "keyboard"

SERVICE_KEYBOARD_VOLUME_UP = "volume_up"
SERVICE_KEYBOARD_VOLUME_DOWN = "volume_down"
SERVICE_KEYBOARD_VOLUME_MUTE = "volume_mute"
SERVICE_KEYBOARD_MEDIA_PLAY_PAUSE = "media_play_pause"
SERVICE_KEYBOARD_MEDIA_NEXT_TRACK = "media_next_track"
SERVICE_KEYBOARD_MEDIA_PREV_TRACK = "media_prev_track"


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

    bus.register_service(DOMAIN_KEYBOARD, SERVICE_KEYBOARD_VOLUME_UP,
                         lambda service:
                         keyboard.tap_key(keyboard.volume_up_key))

    bus.register_service(DOMAIN_KEYBOARD, SERVICE_KEYBOARD_VOLUME_DOWN,
                         lambda service:
                         keyboard.tap_key(keyboard.volume_down_key))

    bus.register_service(DOMAIN_KEYBOARD, SERVICE_KEYBOARD_VOLUME_MUTE,
                         lambda service:
                         keyboard.tap_key(keyboard.volume_mute_key))

    bus.register_service(DOMAIN_KEYBOARD, SERVICE_KEYBOARD_MEDIA_PLAY_PAUSE,
                         lambda service:
                         keyboard.tap_key(keyboard.media_play_pause_key))

    bus.register_service(DOMAIN_KEYBOARD, SERVICE_KEYBOARD_MEDIA_NEXT_TRACK,
                         lambda service:
                         keyboard.tap_key(keyboard.media_next_track_key))

    bus.register_service(DOMAIN_KEYBOARD, SERVICE_KEYBOARD_MEDIA_PREV_TRACK,
                         lambda service:
                         keyboard.tap_key(keyboard.media_prev_track_key))

    return True
