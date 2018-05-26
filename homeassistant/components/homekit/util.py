"""Collection of useful functions for the HomeKit component."""
import logging

import voluptuous as vol

import homeassistant.components.media_player as media_player
from homeassistant.core import split_entity_id
from homeassistant.const import (
    ATTR_CODE, ATTR_SUPPORTED_FEATURES, CONF_MODE, CONF_NAME, TEMP_CELSIUS)
import homeassistant.helpers.config_validation as cv
import homeassistant.util.temperature as temp_util
from .const import (
    HOMEKIT_NOTIFY_ID, FEATURE_ON_OFF, FEATURE_PLAY_PAUSE, FEATURE_PLAY_STOP,
    FEATURE_TOGGLE_MUTE)

_LOGGER = logging.getLogger(__name__)

MEDIA_PLAYER_MODES = (FEATURE_ON_OFF, FEATURE_PLAY_PAUSE, FEATURE_PLAY_STOP,
                      FEATURE_TOGGLE_MUTE)

BASIC_INFO_SCHEMA = vol.Schema({
    vol.Optional(CONF_NAME): cv.string,
})


CODE_SCHEMA = BASIC_INFO_SCHEMA.extend({
    vol.Optional(ATTR_CODE, default=None): vol.Any(None, cv.string),
})


def validate_entity_config(values):
    """Validate config entry for CONF_ENTITY."""
    entities = {}
    for entity_id, config in values.items():
        entity = cv.entity_id(entity_id)
        domain, _ = split_entity_id(entity)

        if not isinstance(config, dict):
            raise vol.Invalid('The configuration for {} must be '
                              ' a dictionary.'.format(entity))

        if domain in ('alarm_control_panel', 'lock'):
            config = CODE_SCHEMA(config)

        elif domain == media_player.DOMAIN:
            mode = config.get(CONF_MODE)
            config[CONF_MODE] = cv.ensure_list(mode)
            for key in config[CONF_MODE]:
                if key not in MEDIA_PLAYER_MODES:
                    raise vol.Invalid(
                        'Invalid mode: "{}", valid modes are: "{}".'
                        .format(key, MEDIA_PLAYER_MODES))

        else:
            config = BASIC_INFO_SCHEMA(config)

        entities[entity] = config
    return entities


def validate_media_player_features(state, config):
    """Validate features for media players."""
    features = state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)

    supported_modes = []
    if features & (media_player.SUPPORT_TURN_ON |
                   media_player.SUPPORT_TURN_OFF):
        supported_modes.append(FEATURE_ON_OFF)
    if features & (media_player.SUPPORT_PLAY | media_player.SUPPORT_PAUSE):
        supported_modes.append(FEATURE_PLAY_PAUSE)
    if features & (media_player.SUPPORT_PLAY | media_player.SUPPORT_STOP):
        supported_modes.append(FEATURE_PLAY_STOP)
    if features & media_player.SUPPORT_VOLUME_MUTE:
        supported_modes.append(FEATURE_TOGGLE_MUTE)

    if not config.get(CONF_MODE):
        config[CONF_MODE] = supported_modes
        return

    for mode in config[CONF_MODE]:
        if mode not in supported_modes:
            raise vol.Invalid('"{}" does not support mode: "{}".'
                              .format(state.entity_id, mode))


def show_setup_message(hass, pincode):
    """Display persistent notification with setup information."""
    pin = pincode.decode()
    _LOGGER.info('Pincode: %s', pin)
    message = 'To setup Home Assistant in the Home App, enter the ' \
              'following code:\n### {}'.format(pin)
    hass.components.persistent_notification.create(
        message, 'HomeKit Setup', HOMEKIT_NOTIFY_ID)


def dismiss_setup_message(hass):
    """Dismiss persistent notification and remove QR code."""
    hass.components.persistent_notification.dismiss(HOMEKIT_NOTIFY_ID)


def convert_to_float(state):
    """Return float of state, catch errors."""
    try:
        return float(state)
    except (ValueError, TypeError):
        return None


def temperature_to_homekit(temperature, unit):
    """Convert temperature to Celsius for HomeKit."""
    return round(temp_util.convert(temperature, unit, TEMP_CELSIUS), 1)


def temperature_to_states(temperature, unit):
    """Convert temperature back from Celsius to Home Assistant unit."""
    return round(temp_util.convert(temperature, TEMP_CELSIUS, unit), 1)


def density_to_air_quality(density):
    """Map PM2.5 density to HomeKit AirQuality level."""
    if density <= 35:
        return 1
    elif density <= 75:
        return 2
    elif density <= 115:
        return 3
    elif density <= 150:
        return 4
    return 5
