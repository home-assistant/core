"""
Provides functionality to emulate keyboard presses on host machine.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/keyboard/
"""
import voluptuous as vol

from homeassistant.const import (
    SERVICE_MEDIA_NEXT_TRACK, SERVICE_MEDIA_PLAY_PAUSE,
    SERVICE_MEDIA_PREVIOUS_TRACK, SERVICE_VOLUME_DOWN, SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_UP)

REQUIREMENTS = ['pyuserinput==0.1.11']

DOMAIN = 'keyboard'

TAP_KEY_SCHEMA = vol.Schema({})


def setup(hass, config):
    """Listen for keyboard events."""
    # pylint: disable=import-error
    import pykeyboard

    keyboard = pykeyboard.PyKeyboard()
    keyboard.special_key_assignment()

    hass.services.register(DOMAIN, SERVICE_VOLUME_UP,
                           lambda service:
                           keyboard.tap_key(keyboard.volume_up_key),
                           schema=TAP_KEY_SCHEMA)

    hass.services.register(DOMAIN, SERVICE_VOLUME_DOWN,
                           lambda service:
                           keyboard.tap_key(keyboard.volume_down_key),
                           schema=TAP_KEY_SCHEMA)

    hass.services.register(DOMAIN, SERVICE_VOLUME_MUTE,
                           lambda service:
                           keyboard.tap_key(keyboard.volume_mute_key),
                           schema=TAP_KEY_SCHEMA)

    hass.services.register(DOMAIN, SERVICE_MEDIA_PLAY_PAUSE,
                           lambda service:
                           keyboard.tap_key(keyboard.media_play_pause_key),
                           schema=TAP_KEY_SCHEMA)

    hass.services.register(DOMAIN, SERVICE_MEDIA_NEXT_TRACK,
                           lambda service:
                           keyboard.tap_key(keyboard.media_next_track_key),
                           schema=TAP_KEY_SCHEMA)

    hass.services.register(DOMAIN, SERVICE_MEDIA_PREVIOUS_TRACK,
                           lambda service:
                           keyboard.tap_key(keyboard.media_prev_track_key),
                           schema=TAP_KEY_SCHEMA)
    return True
