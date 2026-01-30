"""Constants for the Lyngdorf integration."""

from homeassistant.components.media_player import MediaPlayerEntityFeature
from homeassistant.const import Platform

DOMAIN = "lyngdorf"
DEFAULT_DEVICE_NAME = "Lyngdorf MP-60"

VOLUME_MIN = -99.9  # dB
VOLUME_MAX = 20.0  # dB

PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER, Platform.NUMBER, Platform.SELECT]
CONF_RECEIVER = "receiver"
CONF_SERIAL_NUMBER = "serial_number"
CONF_MAKE_MODEL = "make_and_model"
CONF_DEVICE_INFO = "device_info"

MANUFACTURER_LYNGDORF = "Lyngdorf"

SUPPORTED_MANUFACTURERS = [MANUFACTURER_LYNGDORF]  # Steinway todo

SUPPORTED_DEVICES = [{"manufacturer": MANUFACTURER_LYNGDORF, "model": "MP-60"}]

NAME_MAIN_ZONE = "Main Zone"
NAME_ZONE_B = "Zone B"

ICON_VOICE = "mdi:account-voice"
ICON_TRIM_BASS = "mdi:music-clef-bass"
ICON_TRIM_TREBLE = "mdi:music-clef-treble"
ICON_TRIM_HEIGHT = "mdi:wall-sconce-flat"
ICON_TRIM_SURROUND = "mdi:surround-sound"
ICON_TRIM_LFE = "mdi:volume-vibrate"
ICON_TRIM_CENTRE = "mdi:set-center"
ICON_VOICING = "mdi:account-voice"
ICOM_ROOM_PERFECT_POSITION = "mdi:account-voice"
ICON_SOURCE = "mdi:import"
ICON_SOUND_MODE = "mdi:music-note"


CONF_MANUFACTURER = "manufacturer"


FEATURES_MP60_ZONE_B = (
    MediaPlayerEntityFeature.VOLUME_STEP
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.SELECT_SOURCE
)

FEATURES_MP60 = (
    MediaPlayerEntityFeature.VOLUME_STEP
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.SELECT_SOUND_MODE
    | MediaPlayerEntityFeature.SELECT_SOURCE
)
