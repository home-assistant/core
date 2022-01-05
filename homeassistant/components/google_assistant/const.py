"""Constants for Google Assistant."""
from homeassistant.components import (
    binary_sensor,
    cover,
    group,
    humidifier,
    input_boolean,
    input_button,
    input_select,
    media_player,
    script,
    select,
    sensor,
    switch,
)
from homeassistant.const import Platform

DOMAIN = "google_assistant"

GOOGLE_ASSISTANT_API_ENDPOINT = "/api/google_assistant"

CONF_ALIASES = "aliases"
CONF_CLIENT_EMAIL = "client_email"
CONF_ENTITY_CONFIG = "entity_config"
CONF_EXPOSE = "expose"
CONF_EXPOSE_BY_DEFAULT = "expose_by_default"
CONF_EXPOSED_DOMAINS = "exposed_domains"
CONF_PRIVATE_KEY = "private_key"
CONF_PROJECT_ID = "project_id"
CONF_REPORT_STATE = "report_state"
CONF_ROOM_HINT = "room"
CONF_SECURE_DEVICES_PIN = "secure_devices_pin"
CONF_SERVICE_ACCOUNT = "service_account"

DEFAULT_EXPOSE_BY_DEFAULT = True
DEFAULT_EXPOSED_DOMAINS = [
    "alarm_control_panel",
    "binary_sensor",
    "climate",
    "cover",
    "fan",
    "group",
    "humidifier",
    "input_boolean",
    "input_select",
    "light",
    "lock",
    "media_player",
    "scene",
    "script",
    "select",
    "sensor",
    "switch",
    "vacuum",
]

# https://developers.google.com/assistant/smarthome/guides
PREFIX_TYPES = "action.devices.types."
TYPE_ALARM = f"{PREFIX_TYPES}SECURITYSYSTEM"
TYPE_AWNING = f"{PREFIX_TYPES}AWNING"
TYPE_BLINDS = f"{PREFIX_TYPES}BLINDS"
TYPE_CAMERA = f"{PREFIX_TYPES}CAMERA"
TYPE_CURTAIN = f"{PREFIX_TYPES}CURTAIN"
TYPE_DEHUMIDIFIER = f"{PREFIX_TYPES}DEHUMIDIFIER"
TYPE_DOOR = f"{PREFIX_TYPES}DOOR"
TYPE_FAN = f"{PREFIX_TYPES}FAN"
TYPE_GARAGE = f"{PREFIX_TYPES}GARAGE"
TYPE_HUMIDIFIER = f"{PREFIX_TYPES}HUMIDIFIER"
TYPE_LIGHT = f"{PREFIX_TYPES}LIGHT"
TYPE_LOCK = f"{PREFIX_TYPES}LOCK"
TYPE_OUTLET = f"{PREFIX_TYPES}OUTLET"
TYPE_RECEIVER = f"{PREFIX_TYPES}AUDIO_VIDEO_RECEIVER"
TYPE_SCENE = f"{PREFIX_TYPES}SCENE"
TYPE_SENSOR = f"{PREFIX_TYPES}SENSOR"
TYPE_SETTOP = f"{PREFIX_TYPES}SETTOP"
TYPE_SHUTTER = f"{PREFIX_TYPES}SHUTTER"
TYPE_SPEAKER = f"{PREFIX_TYPES}SPEAKER"
TYPE_SWITCH = f"{PREFIX_TYPES}SWITCH"
TYPE_THERMOSTAT = f"{PREFIX_TYPES}THERMOSTAT"
TYPE_TV = f"{PREFIX_TYPES}TV"
TYPE_VACUUM = f"{PREFIX_TYPES}VACUUM"

SERVICE_REQUEST_SYNC = "request_sync"
HOMEGRAPH_URL = "https://homegraph.googleapis.com/"
HOMEGRAPH_SCOPE = "https://www.googleapis.com/auth/homegraph"
HOMEGRAPH_TOKEN_URL = "https://accounts.google.com/o/oauth2/token"
REQUEST_SYNC_BASE_URL = f"{HOMEGRAPH_URL}v1/devices:requestSync"
REPORT_STATE_BASE_URL = f"{HOMEGRAPH_URL}v1/devices:reportStateAndNotification"

# Error codes used for SmartHomeError class
# https://developers.google.com/actions/reference/smarthome/errors-exceptions
ERR_ALREADY_ARMED = "alreadyArmed"
ERR_ALREADY_DISARMED = "alreadyDisarmed"
ERR_ALREADY_STOPPED = "alreadyStopped"
ERR_CHALLENGE_NEEDED = "challengeNeeded"
ERR_CHALLENGE_NOT_SETUP = "challengeFailedNotSetup"
ERR_DEVICE_NOT_FOUND = "deviceNotFound"
ERR_DEVICE_OFFLINE = "deviceOffline"
ERR_FUNCTION_NOT_SUPPORTED = "functionNotSupported"
ERR_NO_AVAILABLE_CHANNEL = "noAvailableChannel"
ERR_NOT_SUPPORTED = "notSupported"
ERR_PIN_INCORRECT = "pinIncorrect"
ERR_PROTOCOL_ERROR = "protocolError"
ERR_TOO_MANY_FAILED_ATTEMPTS = "tooManyFailedAttempts"
ERR_UNKNOWN_ERROR = "unknownError"
ERR_UNSUPPORTED_INPUT = "unsupportedInput"
ERR_USER_CANCELLED = "userCancelled"
ERR_VALUE_OUT_OF_RANGE = "valueOutOfRange"

# Event types
EVENT_COMMAND_RECEIVED = "google_assistant_command"
EVENT_QUERY_RECEIVED = "google_assistant_query"
EVENT_SYNC_RECEIVED = "google_assistant_sync"

DOMAIN_TO_GOOGLE_TYPES = {
    Platform.ALARM_CONTROL_PANEL: TYPE_ALARM,
    Platform.BUTTON: TYPE_SCENE,
    Platform.CAMERA: TYPE_CAMERA,
    Platform.CLIMATE: TYPE_THERMOSTAT,
    Platform.COVER: TYPE_BLINDS,
    Platform.FAN: TYPE_FAN,
    group.DOMAIN: TYPE_SWITCH,
    Platform.HUMIDIFIER: TYPE_HUMIDIFIER,
    input_boolean.DOMAIN: TYPE_SWITCH,
    input_button.DOMAIN: TYPE_SCENE,
    input_select.DOMAIN: TYPE_SENSOR,
    Platform.LIGHT: TYPE_LIGHT,
    Platform.LOCK: TYPE_LOCK,
    Platform.MEDIA_PLAYER: TYPE_SETTOP,
    Platform.SCENE: TYPE_SCENE,
    script.DOMAIN: TYPE_SCENE,
    select.DOMAIN: TYPE_SENSOR,
    Platform.SENSOR: TYPE_SENSOR,
    Platform.SWITCH: TYPE_SWITCH,
    Platform.VACUUM: TYPE_VACUUM,
}

DEVICE_CLASS_TO_GOOGLE_TYPES = {
    (Platform.BINARY_SENSOR, binary_sensor.BinarySensorDeviceClass.DOOR): TYPE_DOOR,
    (Platform.BINARY_SENSOR, binary_sensor.BinarySensorDeviceClass.LOCK): TYPE_SENSOR,
    (
        Platform.BINARY_SENSOR,
        binary_sensor.BinarySensorDeviceClass.OPENING,
    ): TYPE_SENSOR,
    (Platform.BINARY_SENSOR, binary_sensor.BinarySensorDeviceClass.WINDOW): TYPE_SENSOR,
    (
        Platform.BINARY_SENSOR,
        binary_sensor.BinarySensorDeviceClass.GARAGE_DOOR,
    ): TYPE_GARAGE,
    (Platform.COVER, cover.CoverDeviceClass.AWNING): TYPE_AWNING,
    (Platform.COVER, cover.CoverDeviceClass.CURTAIN): TYPE_CURTAIN,
    (Platform.COVER, cover.CoverDeviceClass.DOOR): TYPE_DOOR,
    (Platform.COVER, cover.CoverDeviceClass.GARAGE): TYPE_GARAGE,
    (Platform.COVER, cover.CoverDeviceClass.GATE): TYPE_GARAGE,
    (Platform.COVER, cover.CoverDeviceClass.SHUTTER): TYPE_SHUTTER,
    (
        Platform.HUMIDIFIER,
        humidifier.HumidifierDeviceClass.DEHUMIDIFIER,
    ): TYPE_DEHUMIDIFIER,
    (humidifier.DOMAIN, humidifier.HumidifierDeviceClass.HUMIDIFIER): TYPE_HUMIDIFIER,
    (media_player.DOMAIN, media_player.MediaPlayerDeviceClass.RECEIVER): TYPE_RECEIVER,
    (media_player.DOMAIN, media_player.MediaPlayerDeviceClass.SPEAKER): TYPE_SPEAKER,
    (media_player.DOMAIN, media_player.MediaPlayerDeviceClass.TV): TYPE_TV,
    (sensor.DOMAIN, sensor.SensorDeviceClass.HUMIDITY): TYPE_SENSOR,
    (sensor.DOMAIN, sensor.SensorDeviceClass.TEMPERATURE): TYPE_SENSOR,
    (switch.DOMAIN, switch.SwitchDeviceClass.OUTLET): TYPE_OUTLET,
    (switch.DOMAIN, switch.SwitchDeviceClass.SWITCH): TYPE_SWITCH,
}

CHALLENGE_ACK_NEEDED = "ackNeeded"
CHALLENGE_FAILED_PIN_NEEDED = "challengeFailedPinNeeded"
CHALLENGE_PIN_NEEDED = "pinNeeded"

STORE_AGENT_USER_IDS = "agent_user_ids"

SOURCE_CLOUD = "cloud"
SOURCE_LOCAL = "local"

NOT_EXPOSE_LOCAL = {TYPE_ALARM, TYPE_LOCK}
