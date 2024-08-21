"""Constants used by vizio component."""

from pyvizio.const import (
    DEVICE_CLASS_SPEAKER as VIZIO_DEVICE_CLASS_SPEAKER,
    DEVICE_CLASS_TV as VIZIO_DEVICE_CLASS_TV,
)
import voluptuous as vol

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntityFeature,
)
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_DEVICE_CLASS,
    CONF_EXCLUDE,
    CONF_HOST,
    CONF_INCLUDE,
    CONF_NAME,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import VolDictType

SERVICE_UPDATE_SETTING = "update_setting"

ATTR_SETTING_TYPE = "setting_type"
ATTR_SETTING_NAME = "setting_name"
ATTR_NEW_VALUE = "new_value"

UPDATE_SETTING_SCHEMA: VolDictType = {
    vol.Required(ATTR_SETTING_TYPE): vol.All(cv.string, vol.Lower, cv.slugify),
    vol.Required(ATTR_SETTING_NAME): vol.All(cv.string, vol.Lower, cv.slugify),
    vol.Required(ATTR_NEW_VALUE): vol.Any(vol.Coerce(int), cv.string),
}

CONF_ADDITIONAL_CONFIGS = "additional_configs"
CONF_APP_ID = "APP_ID"
CONF_APPS = "apps"
CONF_APPS_TO_INCLUDE_OR_EXCLUDE = "apps_to_include_or_exclude"
CONF_CONFIG = "config"
CONF_INCLUDE_OR_EXCLUDE = "include_or_exclude"
CONF_NAME_SPACE = "NAME_SPACE"
CONF_MESSAGE = "MESSAGE"
CONF_VOLUME_STEP = "volume_step"

DEFAULT_DEVICE_CLASS = MediaPlayerDeviceClass.TV
DEFAULT_NAME = "Vizio SmartCast"
DEFAULT_TIMEOUT = 8
DEFAULT_VOLUME_STEP = 1

DEVICE_ID = "pyvizio"

DOMAIN = "vizio"

COMMON_SUPPORTED_COMMANDS = (
    MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.SELECT_SOURCE
    | MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_STEP
)

SUPPORTED_COMMANDS = {
    MediaPlayerDeviceClass.SPEAKER: COMMON_SUPPORTED_COMMANDS,
    MediaPlayerDeviceClass.TV: (
        COMMON_SUPPORTED_COMMANDS
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
    ),
}

VIZIO_SOUND_MODE = "eq"
VIZIO_AUDIO_SETTINGS = "audio"
VIZIO_MUTE_ON = "on"
VIZIO_VOLUME = "volume"
VIZIO_MUTE = "mute"

# Since Vizio component relies on device class, this dict will ensure that changes to
# the values of DEVICE_CLASS_SPEAKER or DEVICE_CLASS_TV don't require changes to pyvizio.
VIZIO_DEVICE_CLASSES = {
    MediaPlayerDeviceClass.SPEAKER: VIZIO_DEVICE_CLASS_SPEAKER,
    MediaPlayerDeviceClass.TV: VIZIO_DEVICE_CLASS_TV,
}

VIZIO_SCHEMA = {
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_ACCESS_TOKEN): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_DEVICE_CLASS, default=DEFAULT_DEVICE_CLASS): vol.All(
        cv.string,
        vol.Lower,
        vol.In([MediaPlayerDeviceClass.TV, MediaPlayerDeviceClass.SPEAKER]),
    ),
    vol.Optional(CONF_VOLUME_STEP, default=DEFAULT_VOLUME_STEP): vol.All(
        vol.Coerce(int), vol.Range(min=1, max=10)
    ),
    vol.Optional(CONF_APPS): vol.All(
        {
            vol.Exclusive(CONF_INCLUDE, "apps_filter"): vol.All(
                cv.ensure_list, [cv.string]
            ),
            vol.Exclusive(CONF_EXCLUDE, "apps_filter"): vol.All(
                cv.ensure_list, [cv.string]
            ),
            vol.Optional(CONF_ADDITIONAL_CONFIGS): vol.All(
                cv.ensure_list,
                [
                    {
                        vol.Required(CONF_NAME): cv.string,
                        vol.Required(CONF_CONFIG): {
                            vol.Required(CONF_APP_ID): cv.string,
                            vol.Required(CONF_NAME_SPACE): vol.Coerce(int),
                            vol.Optional(CONF_MESSAGE, default=None): vol.Or(
                                cv.string, None
                            ),
                        },
                    },
                ],
            ),
        },
        cv.has_at_least_one_key(CONF_INCLUDE, CONF_EXCLUDE, CONF_ADDITIONAL_CONFIGS),
    ),
}
