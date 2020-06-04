"""Collection of useful functions for the HomeKit component."""
from collections import OrderedDict, namedtuple
import io
import ipaddress
import logging
import os
import re
import secrets
import socket

import pyqrcode
import voluptuous as vol

from homeassistant.components import binary_sensor, fan, media_player, sensor
from homeassistant.const import (
    ATTR_CODE,
    ATTR_SUPPORTED_FEATURES,
    CONF_NAME,
    CONF_TYPE,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant, split_entity_id
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.storage import STORAGE_DIR
import homeassistant.util.temperature as temp_util

from .const import (
    AUDIO_CODEC_COPY,
    AUDIO_CODEC_OPUS,
    CONF_AUDIO_CODEC,
    CONF_AUDIO_MAP,
    CONF_AUDIO_PACKET_SIZE,
    CONF_FEATURE,
    CONF_FEATURE_LIST,
    CONF_LINKED_BATTERY_CHARGING_SENSOR,
    CONF_LINKED_BATTERY_SENSOR,
    CONF_LINKED_MOTION_SENSOR,
    CONF_LOW_BATTERY_THRESHOLD,
    CONF_MAX_FPS,
    CONF_MAX_HEIGHT,
    CONF_MAX_WIDTH,
    CONF_STREAM_ADDRESS,
    CONF_STREAM_SOURCE,
    CONF_SUPPORT_AUDIO,
    CONF_VIDEO_CODEC,
    CONF_VIDEO_MAP,
    CONF_VIDEO_PACKET_SIZE,
    DEFAULT_AUDIO_CODEC,
    DEFAULT_AUDIO_MAP,
    DEFAULT_AUDIO_PACKET_SIZE,
    DEFAULT_LOW_BATTERY_THRESHOLD,
    DEFAULT_MAX_FPS,
    DEFAULT_MAX_HEIGHT,
    DEFAULT_MAX_WIDTH,
    DEFAULT_SUPPORT_AUDIO,
    DEFAULT_VIDEO_CODEC,
    DEFAULT_VIDEO_MAP,
    DEFAULT_VIDEO_PACKET_SIZE,
    DOMAIN,
    FEATURE_ON_OFF,
    FEATURE_PLAY_PAUSE,
    FEATURE_PLAY_STOP,
    FEATURE_TOGGLE_MUTE,
    HOMEKIT_FILE,
    HOMEKIT_PAIRING_QR,
    HOMEKIT_PAIRING_QR_SECRET,
    TYPE_FAUCET,
    TYPE_OUTLET,
    TYPE_SHOWER,
    TYPE_SPRINKLER,
    TYPE_SWITCH,
    TYPE_VALVE,
    VIDEO_CODEC_COPY,
    VIDEO_CODEC_H264_OMX,
    VIDEO_CODEC_LIBX264,
)

_LOGGER = logging.getLogger(__name__)

MAX_PORT = 65535
VALID_VIDEO_CODECS = [VIDEO_CODEC_LIBX264, VIDEO_CODEC_H264_OMX, AUDIO_CODEC_COPY]
VALID_AUDIO_CODECS = [AUDIO_CODEC_OPUS, VIDEO_CODEC_COPY]

BASIC_INFO_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_LINKED_BATTERY_SENSOR): cv.entity_domain(sensor.DOMAIN),
        vol.Optional(CONF_LINKED_BATTERY_CHARGING_SENSOR): cv.entity_domain(
            binary_sensor.DOMAIN
        ),
        vol.Optional(
            CONF_LOW_BATTERY_THRESHOLD, default=DEFAULT_LOW_BATTERY_THRESHOLD
        ): cv.positive_int,
    }
)

FEATURE_SCHEMA = BASIC_INFO_SCHEMA.extend(
    {vol.Optional(CONF_FEATURE_LIST, default=None): cv.ensure_list}
)

CAMERA_SCHEMA = BASIC_INFO_SCHEMA.extend(
    {
        vol.Optional(CONF_STREAM_ADDRESS): vol.All(ipaddress.ip_address, cv.string),
        vol.Optional(CONF_STREAM_SOURCE): cv.string,
        vol.Optional(CONF_AUDIO_CODEC, default=DEFAULT_AUDIO_CODEC): vol.In(
            VALID_AUDIO_CODECS
        ),
        vol.Optional(CONF_SUPPORT_AUDIO, default=DEFAULT_SUPPORT_AUDIO): cv.boolean,
        vol.Optional(CONF_MAX_WIDTH, default=DEFAULT_MAX_WIDTH): cv.positive_int,
        vol.Optional(CONF_MAX_HEIGHT, default=DEFAULT_MAX_HEIGHT): cv.positive_int,
        vol.Optional(CONF_MAX_FPS, default=DEFAULT_MAX_FPS): cv.positive_int,
        vol.Optional(CONF_AUDIO_MAP, default=DEFAULT_AUDIO_MAP): cv.string,
        vol.Optional(CONF_VIDEO_MAP, default=DEFAULT_VIDEO_MAP): cv.string,
        vol.Optional(CONF_VIDEO_CODEC, default=DEFAULT_VIDEO_CODEC): vol.In(
            VALID_VIDEO_CODECS
        ),
        vol.Optional(
            CONF_AUDIO_PACKET_SIZE, default=DEFAULT_AUDIO_PACKET_SIZE
        ): cv.positive_int,
        vol.Optional(
            CONF_VIDEO_PACKET_SIZE, default=DEFAULT_VIDEO_PACKET_SIZE
        ): cv.positive_int,
        vol.Optional(CONF_LINKED_MOTION_SENSOR): cv.entity_domain(binary_sensor.DOMAIN),
    }
)

CODE_SCHEMA = BASIC_INFO_SCHEMA.extend(
    {vol.Optional(ATTR_CODE, default=None): vol.Any(None, cv.string)}
)

MEDIA_PLAYER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_FEATURE): vol.All(
            cv.string,
            vol.In(
                (
                    FEATURE_ON_OFF,
                    FEATURE_PLAY_PAUSE,
                    FEATURE_PLAY_STOP,
                    FEATURE_TOGGLE_MUTE,
                )
            ),
        )
    }
)

SWITCH_TYPE_SCHEMA = BASIC_INFO_SCHEMA.extend(
    {
        vol.Optional(CONF_TYPE, default=TYPE_SWITCH): vol.All(
            cv.string,
            vol.In(
                (
                    TYPE_FAUCET,
                    TYPE_OUTLET,
                    TYPE_SHOWER,
                    TYPE_SPRINKLER,
                    TYPE_SWITCH,
                    TYPE_VALVE,
                )
            ),
        )
    }
)


HOMEKIT_CHAR_TRANSLATIONS = {
    0: " ",  # nul
    10: " ",  # nl
    13: " ",  # cr
    33: "-",  # !
    34: " ",  # "
    36: "-",  # $
    37: "-",  # %
    40: "-",  # (
    41: "-",  # )
    42: "-",  # *
    43: "-",  # +
    47: "-",  # /
    58: "-",  # :
    59: "-",  # ;
    60: "-",  # <
    61: "-",  # =
    62: "-",  # >
    63: "-",  # ?
    64: "-",  # @
    91: "-",  # [
    92: "-",  # \
    93: "-",  # ]
    94: "-",  # ^
    95: " ",  # _
    96: "-",  # `
    123: "-",  # {
    124: "-",  # |
    125: "-",  # }
    126: "-",  # ~
    127: "-",  # del
}


def validate_entity_config(values):
    """Validate config entry for CONF_ENTITY."""
    if not isinstance(values, dict):
        raise vol.Invalid("expected a dictionary")

    entities = {}
    for entity_id, config in values.items():
        entity = cv.entity_id(entity_id)
        domain, _ = split_entity_id(entity)

        if not isinstance(config, dict):
            raise vol.Invalid(f"The configuration for {entity} must be a dictionary.")

        if domain in ("alarm_control_panel", "lock"):
            config = CODE_SCHEMA(config)

        elif domain == media_player.const.DOMAIN:
            config = FEATURE_SCHEMA(config)
            feature_list = {}
            for feature in config[CONF_FEATURE_LIST]:
                params = MEDIA_PLAYER_SCHEMA(feature)
                key = params.pop(CONF_FEATURE)
                if key in feature_list:
                    raise vol.Invalid(f"A feature can be added only once for {entity}")
                feature_list[key] = params
            config[CONF_FEATURE_LIST] = feature_list

        elif domain == "camera":
            config = CAMERA_SCHEMA(config)

        elif domain == "switch":
            config = SWITCH_TYPE_SCHEMA(config)

        else:
            config = BASIC_INFO_SCHEMA(config)

        entities[entity] = config
    return entities


def get_media_player_features(state):
    """Determine features for media players."""
    features = state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)

    supported_modes = []
    if features & (
        media_player.const.SUPPORT_TURN_ON | media_player.const.SUPPORT_TURN_OFF
    ):
        supported_modes.append(FEATURE_ON_OFF)
    if features & (media_player.const.SUPPORT_PLAY | media_player.const.SUPPORT_PAUSE):
        supported_modes.append(FEATURE_PLAY_PAUSE)
    if features & (media_player.const.SUPPORT_PLAY | media_player.const.SUPPORT_STOP):
        supported_modes.append(FEATURE_PLAY_STOP)
    if features & media_player.const.SUPPORT_VOLUME_MUTE:
        supported_modes.append(FEATURE_TOGGLE_MUTE)
    return supported_modes


def validate_media_player_features(state, feature_list):
    """Validate features for media players."""
    supported_modes = get_media_player_features(state)

    if not supported_modes:
        _LOGGER.error("%s does not support any media_player features", state.entity_id)
        return False

    if not feature_list:
        # Auto detected
        return True

    error_list = []
    for feature in feature_list:
        if feature not in supported_modes:
            error_list.append(feature)

    if error_list:
        _LOGGER.error(
            "%s does not support media_player features: %s", state.entity_id, error_list
        )
        return False
    return True


SpeedRange = namedtuple("SpeedRange", ("start", "target"))
SpeedRange.__doc__ += """ Maps Home Assistant speed \
values to percentage based HomeKit speeds.
start: Start of the range (inclusive).
target: Percentage to use to determine HomeKit percentages \
from HomeAssistant speed.
"""


class HomeKitSpeedMapping:
    """Supports conversion between Home Assistant and HomeKit fan speeds."""

    def __init__(self, speed_list):
        """Initialize a new SpeedMapping object."""
        if speed_list[0] != fan.SPEED_OFF:
            _LOGGER.warning(
                "%s does not contain the speed setting "
                "%s as its first element. "
                "Assuming that %s is equivalent to 'off'.",
                speed_list,
                fan.SPEED_OFF,
                speed_list[0],
            )
        self.speed_ranges = OrderedDict()
        list_size = len(speed_list)
        for index, speed in enumerate(speed_list):
            # By dividing by list_size -1 the following
            # desired attributes hold true:
            # * index = 0 => 0%, equal to "off"
            # * index = len(speed_list) - 1 => 100 %
            # * all other indices are equally distributed
            target = index * 100 / (list_size - 1)
            start = index * 100 / list_size
            self.speed_ranges[speed] = SpeedRange(start, target)

    def speed_to_homekit(self, speed):
        """Map Home Assistant speed state to HomeKit speed."""
        if speed is None:
            return None
        speed_range = self.speed_ranges[speed]
        return round(speed_range.target)

    def speed_to_states(self, speed):
        """Map HomeKit speed to Home Assistant speed state."""
        for state, speed_range in reversed(self.speed_ranges.items()):
            if speed_range.start <= speed:
                return state
        return list(self.speed_ranges.keys())[0]


def show_setup_message(hass, entry_id, bridge_name, pincode, uri):
    """Display persistent notification with setup information."""
    pin = pincode.decode()
    _LOGGER.info("Pincode: %s", pin)

    buffer = io.BytesIO()
    url = pyqrcode.create(uri)
    url.svg(buffer, scale=5)
    pairing_secret = secrets.token_hex(32)

    hass.data[DOMAIN][entry_id][HOMEKIT_PAIRING_QR] = buffer.getvalue()
    hass.data[DOMAIN][entry_id][HOMEKIT_PAIRING_QR_SECRET] = pairing_secret

    message = (
        f"To set up {bridge_name} in the Home App, "
        f"scan the QR code or enter the following code:\n"
        f"### {pin}\n"
        f"![image](/api/homekit/pairingqr?{entry_id}-{pairing_secret})"
    )
    hass.components.persistent_notification.create(
        message, "HomeKit Bridge Setup", entry_id
    )


def dismiss_setup_message(hass, entry_id):
    """Dismiss persistent notification and remove QR code."""
    hass.components.persistent_notification.dismiss(entry_id)


def convert_to_float(state):
    """Return float of state, catch errors."""
    try:
        return float(state)
    except (ValueError, TypeError):
        return None


def cleanup_name_for_homekit(name):
    """Ensure the name of the device will not crash homekit."""
    #
    # This is not a security measure.
    #
    # UNICODE_EMOJI is also not allowed but that
    # likely isn't a problem
    return name.translate(HOMEKIT_CHAR_TRANSLATIONS)


def temperature_to_homekit(temperature, unit):
    """Convert temperature to Celsius for HomeKit."""
    return round(temp_util.convert(temperature, unit, TEMP_CELSIUS), 1)


def temperature_to_states(temperature, unit):
    """Convert temperature back from Celsius to Home Assistant unit."""
    return round(temp_util.convert(temperature, TEMP_CELSIUS, unit) * 2) / 2


def density_to_air_quality(density):
    """Map PM2.5 density to HomeKit AirQuality level."""
    if density <= 35:
        return 1
    if density <= 75:
        return 2
    if density <= 115:
        return 3
    if density <= 150:
        return 4
    return 5


def get_persist_filename_for_entry_id(entry_id: str):
    """Determine the filename of the homekit state file."""
    return f"{DOMAIN}.{entry_id}.state"


def get_aid_storage_filename_for_entry_id(entry_id: str):
    """Determine the ilename of homekit aid storage file."""
    return f"{DOMAIN}.{entry_id}.aids"


def get_persist_fullpath_for_entry_id(hass: HomeAssistant, entry_id: str):
    """Determine the path to the homekit state file."""
    return hass.config.path(STORAGE_DIR, get_persist_filename_for_entry_id(entry_id))


def get_aid_storage_fullpath_for_entry_id(hass: HomeAssistant, entry_id: str):
    """Determine the path to the homekit aid storage file."""
    return hass.config.path(
        STORAGE_DIR, get_aid_storage_filename_for_entry_id(entry_id)
    )


def format_sw_version(version):
    """Extract the version string in a format homekit can consume."""
    match = re.search(r"([0-9]+)(\.[0-9]+)?(\.[0-9]+)?", str(version).replace("-", "."))
    if match:
        return match.group(0)
    return None


def migrate_filesystem_state_data_for_primary_imported_entry_id(
    hass: HomeAssistant, entry_id: str
):
    """Migrate the old paths to the storage directory."""
    legacy_persist_file_path = hass.config.path(HOMEKIT_FILE)
    if os.path.exists(legacy_persist_file_path):
        os.rename(
            legacy_persist_file_path, get_persist_fullpath_for_entry_id(hass, entry_id)
        )

    legacy_aid_storage_path = hass.config.path(STORAGE_DIR, "homekit.aids")
    if os.path.exists(legacy_aid_storage_path):
        os.rename(
            legacy_aid_storage_path,
            get_aid_storage_fullpath_for_entry_id(hass, entry_id),
        )


def remove_state_files_for_entry_id(hass: HomeAssistant, entry_id: str):
    """Remove the state files from disk."""
    persist_file_path = get_persist_fullpath_for_entry_id(hass, entry_id)
    aid_storage_path = get_aid_storage_fullpath_for_entry_id(hass, entry_id)
    os.unlink(persist_file_path)
    if os.path.exists(aid_storage_path):
        os.unlink(aid_storage_path)
    return True


def _get_test_socket():
    """Create a socket to test binding ports."""
    test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    test_socket.setblocking(False)
    test_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    return test_socket


def port_is_available(port: int):
    """Check to see if a port is available."""
    test_socket = _get_test_socket()
    try:
        test_socket.bind(("", port))
    except OSError:
        return False

    return True


def find_next_available_port(start_port: int):
    """Find the next available port starting with the given port."""
    test_socket = _get_test_socket()
    for port in range(start_port, MAX_PORT):
        try:
            test_socket.bind(("", port))
            return port
        except OSError:
            if port == MAX_PORT:
                raise
            continue


def pid_is_alive(pid):
    """Check to see if a process is alive."""
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        pass
    return False
