"""Constants for Google Assistant."""
from homeassistant.components import (
    alarm_control_panel,
    binary_sensor,
    camera,
    climate,
    cover,
    fan,
    group,
    humidifier,
    input_boolean,
    input_select,
    light,
    lock,
    media_player,
    scene,
    script,
    sensor,
    switch,
    vacuum,
)

DOMAIN = "google_assistant"

GOOGLE_ASSISTANT_API_ENDPOINT = "/api/google_assistant"

CONF_EXPOSE = "expose"
CONF_ENTITY_CONFIG = "entity_config"
CONF_EXPOSE_BY_DEFAULT = "expose_by_default"
CONF_EXPOSED_DOMAINS = "exposed_domains"
CONF_PROJECT_ID = "project_id"
CONF_ALIASES = "aliases"
CONF_API_KEY = "api_key"
CONF_ROOM_HINT = "room"
CONF_ALLOW_UNLOCK = "allow_unlock"
CONF_SECURE_DEVICES_PIN = "secure_devices_pin"
CONF_REPORT_STATE = "report_state"
CONF_SERVICE_ACCOUNT = "service_account"
CONF_CLIENT_EMAIL = "client_email"
CONF_PRIVATE_KEY = "private_key"

DEFAULT_EXPOSE_BY_DEFAULT = True
DEFAULT_EXPOSED_DOMAINS = [
    "climate",
    "cover",
    "fan",
    "group",
    "humidifier",
    "input_boolean",
    "input_select",
    "light",
    "media_player",
    "scene",
    "script",
    "switch",
    "vacuum",
    "lock",
    "binary_sensor",
    "sensor",
    "alarm_control_panel",
]

PREFIX_TYPES = "action.devices.types."
TYPE_CAMERA = f"{PREFIX_TYPES}CAMERA"
TYPE_LIGHT = f"{PREFIX_TYPES}LIGHT"
TYPE_SWITCH = f"{PREFIX_TYPES}SWITCH"
TYPE_VACUUM = f"{PREFIX_TYPES}VACUUM"
TYPE_SCENE = f"{PREFIX_TYPES}SCENE"
TYPE_FAN = f"{PREFIX_TYPES}FAN"
TYPE_THERMOSTAT = f"{PREFIX_TYPES}THERMOSTAT"
TYPE_LOCK = f"{PREFIX_TYPES}LOCK"
TYPE_BLINDS = f"{PREFIX_TYPES}BLINDS"
TYPE_GARAGE = f"{PREFIX_TYPES}GARAGE"
TYPE_OUTLET = f"{PREFIX_TYPES}OUTLET"
TYPE_SENSOR = f"{PREFIX_TYPES}SENSOR"
TYPE_DOOR = f"{PREFIX_TYPES}DOOR"
TYPE_TV = f"{PREFIX_TYPES}TV"
TYPE_SPEAKER = f"{PREFIX_TYPES}SPEAKER"
TYPE_ALARM = f"{PREFIX_TYPES}SECURITYSYSTEM"
TYPE_SETTOP = f"{PREFIX_TYPES}SETTOP"
TYPE_HUMIDIFIER = f"{PREFIX_TYPES}HUMIDIFIER"
TYPE_DEHUMIDIFIER = f"{PREFIX_TYPES}DEHUMIDIFIER"

SERVICE_REQUEST_SYNC = "request_sync"
HOMEGRAPH_URL = "https://homegraph.googleapis.com/"
HOMEGRAPH_SCOPE = "https://www.googleapis.com/auth/homegraph"
HOMEGRAPH_TOKEN_URL = "https://accounts.google.com/o/oauth2/token"
REQUEST_SYNC_BASE_URL = f"{HOMEGRAPH_URL}v1/devices:requestSync"
REPORT_STATE_BASE_URL = f"{HOMEGRAPH_URL}v1/devices:reportStateAndNotification"

# Error codes used for SmartHomeError class
# https://developers.google.com/actions/reference/smarthome/errors-exceptions
ERR_DEVICE_OFFLINE = "deviceOffline"
ERR_DEVICE_NOT_FOUND = "deviceNotFound"
ERR_VALUE_OUT_OF_RANGE = "valueOutOfRange"
ERR_NOT_SUPPORTED = "notSupported"
ERR_PROTOCOL_ERROR = "protocolError"
ERR_UNKNOWN_ERROR = "unknownError"
ERR_FUNCTION_NOT_SUPPORTED = "functionNotSupported"
ERR_UNSUPPORTED_INPUT = "unsupportedInput"

ERR_ALREADY_DISARMED = "alreadyDisarmed"
ERR_ALREADY_ARMED = "alreadyArmed"

ERR_CHALLENGE_NEEDED = "challengeNeeded"
ERR_CHALLENGE_NOT_SETUP = "challengeFailedNotSetup"
ERR_TOO_MANY_FAILED_ATTEMPTS = "tooManyFailedAttempts"
ERR_PIN_INCORRECT = "pinIncorrect"
ERR_USER_CANCELLED = "userCancelled"

# Event types
EVENT_COMMAND_RECEIVED = "google_assistant_command"
EVENT_QUERY_RECEIVED = "google_assistant_query"
EVENT_SYNC_RECEIVED = "google_assistant_sync"

DOMAIN_TO_GOOGLE_TYPES = {
    camera.DOMAIN: TYPE_CAMERA,
    climate.DOMAIN: TYPE_THERMOSTAT,
    cover.DOMAIN: TYPE_BLINDS,
    fan.DOMAIN: TYPE_FAN,
    group.DOMAIN: TYPE_SWITCH,
    humidifier.DOMAIN: TYPE_HUMIDIFIER,
    input_boolean.DOMAIN: TYPE_SWITCH,
    input_select.DOMAIN: TYPE_SENSOR,
    light.DOMAIN: TYPE_LIGHT,
    lock.DOMAIN: TYPE_LOCK,
    media_player.DOMAIN: TYPE_SETTOP,
    scene.DOMAIN: TYPE_SCENE,
    script.DOMAIN: TYPE_SCENE,
    switch.DOMAIN: TYPE_SWITCH,
    vacuum.DOMAIN: TYPE_VACUUM,
    alarm_control_panel.DOMAIN: TYPE_ALARM,
}

DEVICE_CLASS_TO_GOOGLE_TYPES = {
    (cover.DOMAIN, cover.DEVICE_CLASS_GARAGE): TYPE_GARAGE,
    (cover.DOMAIN, cover.DEVICE_CLASS_GATE): TYPE_GARAGE,
    (cover.DOMAIN, cover.DEVICE_CLASS_DOOR): TYPE_DOOR,
    (switch.DOMAIN, switch.DEVICE_CLASS_SWITCH): TYPE_SWITCH,
    (switch.DOMAIN, switch.DEVICE_CLASS_OUTLET): TYPE_OUTLET,
    (binary_sensor.DOMAIN, binary_sensor.DEVICE_CLASS_DOOR): TYPE_DOOR,
    (binary_sensor.DOMAIN, binary_sensor.DEVICE_CLASS_GARAGE_DOOR): TYPE_GARAGE,
    (binary_sensor.DOMAIN, binary_sensor.DEVICE_CLASS_LOCK): TYPE_SENSOR,
    (binary_sensor.DOMAIN, binary_sensor.DEVICE_CLASS_OPENING): TYPE_SENSOR,
    (binary_sensor.DOMAIN, binary_sensor.DEVICE_CLASS_WINDOW): TYPE_SENSOR,
    (media_player.DOMAIN, media_player.DEVICE_CLASS_TV): TYPE_TV,
    (sensor.DOMAIN, sensor.DEVICE_CLASS_TEMPERATURE): TYPE_SENSOR,
    (sensor.DOMAIN, sensor.DEVICE_CLASS_HUMIDITY): TYPE_SENSOR,
    (humidifier.DOMAIN, humidifier.DEVICE_CLASS_HUMIDIFIER): TYPE_HUMIDIFIER,
    (humidifier.DOMAIN, humidifier.DEVICE_CLASS_DEHUMIDIFIER): TYPE_DEHUMIDIFIER,
}

CHALLENGE_ACK_NEEDED = "ackNeeded"
CHALLENGE_PIN_NEEDED = "pinNeeded"
CHALLENGE_FAILED_PIN_NEEDED = "challengeFailedPinNeeded"

STORE_AGENT_USER_IDS = "agent_user_ids"

SOURCE_CLOUD = "cloud"
SOURCE_LOCAL = "local"

NOT_EXPOSE_LOCAL = {TYPE_ALARM, TYPE_LOCK}
