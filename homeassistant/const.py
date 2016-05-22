# coding: utf-8
"""Constants used by Home Assistant components."""

__version__ = "0.20.1"
REQUIRED_PYTHON_VER = (3, 4)

PLATFORM_FORMAT = '{}.{}'

# Can be used to specify a catch all when registering state or event listeners.
MATCH_ALL = '*'

# If no name is specified
DEVICE_DEFAULT_NAME = "Unnamed Device"

WEEKDAYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']

SUN_EVENT_SUNSET = 'sunset'
SUN_EVENT_SUNRISE = 'sunrise'

# #### CONFIG ####
CONF_ABOVE = 'above'
CONF_ACCESS_TOKEN = 'access_token'
CONF_AFTER = 'after'
CONF_ALIAS = 'alias'
CONF_API_KEY = 'api_key'
CONF_BEFORE = 'before'
CONF_BELOW = 'below'
CONF_CONDITION = 'condition'
CONF_CUSTOMIZE = 'customize'
CONF_ELEVATION = 'elevation'
CONF_ENTITY_ID = 'entity_id'
CONF_ENTITY_NAMESPACE = 'entity_namespace'
CONF_EVENT = 'event'
CONF_FILENAME = 'filename'
CONF_HOST = 'host'
CONF_HOSTS = 'hosts'
CONF_ICON = 'icon'
CONF_LATITUDE = 'latitude'
CONF_LONGITUDE = 'longitude'
CONF_MONITORED_CONDITIONS = 'monitored_conditions'
CONF_NAME = 'name'
CONF_OFFSET = 'offset'
CONF_OPTIMISTIC = 'optimistic'
CONF_PASSWORD = 'password'
CONF_PLATFORM = 'platform'
CONF_PORT = 'port'
CONF_SCAN_INTERVAL = 'scan_interval'
CONF_STATE = 'state'
CONF_TEMPERATURE_UNIT = 'temperature_unit'
CONF_TIME_ZONE = 'time_zone'
CONF_USERNAME = 'username'
CONF_VALUE_TEMPLATE = 'value_template'
CONF_WEEKDAY = 'weekday'
CONF_ZONE = 'zone'

# #### EVENTS ####
EVENT_HOMEASSISTANT_START = "homeassistant_start"
EVENT_HOMEASSISTANT_STOP = "homeassistant_stop"
EVENT_STATE_CHANGED = "state_changed"
EVENT_TIME_CHANGED = "time_changed"
EVENT_CALL_SERVICE = "call_service"
EVENT_SERVICE_EXECUTED = "service_executed"
EVENT_PLATFORM_DISCOVERED = "platform_discovered"
EVENT_COMPONENT_LOADED = "component_loaded"
EVENT_SERVICE_REGISTERED = "service_registered"

# #### STATES ####
STATE_ON = 'on'
STATE_OFF = 'off'
STATE_HOME = 'home'
STATE_NOT_HOME = 'not_home'
STATE_UNKNOWN = 'unknown'
STATE_OPEN = 'open'
STATE_CLOSED = 'closed'
STATE_PLAYING = 'playing'
STATE_PAUSED = 'paused'
STATE_IDLE = 'idle'
STATE_STANDBY = 'standby'
STATE_ALARM_DISARMED = 'disarmed'
STATE_ALARM_ARMED_HOME = 'armed_home'
STATE_ALARM_ARMED_AWAY = 'armed_away'
STATE_ALARM_PENDING = 'pending'
STATE_ALARM_TRIGGERED = 'triggered'
STATE_LOCKED = 'locked'
STATE_UNLOCKED = 'unlocked'
STATE_UNAVAILABLE = 'unavailable'

# #### STATE AND EVENT ATTRIBUTES ####
# Contains current time for a TIME_CHANGED event
ATTR_NOW = "now"

# Contains domain, service for a SERVICE_CALL event
ATTR_DOMAIN = "domain"
ATTR_SERVICE = "service"
ATTR_SERVICE_DATA = "service_data"

# Data for a SERVICE_EXECUTED event
ATTR_SERVICE_CALL_ID = "service_call_id"

# Contains one string or a list of strings, each being an entity id
ATTR_ENTITY_ID = 'entity_id'

# String with a friendly name for the entity
ATTR_FRIENDLY_NAME = "friendly_name"

# A picture to represent entity
ATTR_ENTITY_PICTURE = "entity_picture"

# Icon to use in the frontend
ATTR_ICON = "icon"

# The unit of measurement if applicable
ATTR_UNIT_OF_MEASUREMENT = "unit_of_measurement"

# Temperature attribute
ATTR_TEMPERATURE = "temperature"
TEMP_CELCIUS = "°C"
TEMP_CELSIUS = "°C"
TEMP_FAHRENHEIT = "°F"

# Contains the information that is discovered
ATTR_DISCOVERED = "discovered"

# Location of the device/sensor
ATTR_LOCATION = "location"

ATTR_BATTERY_LEVEL = "battery_level"

# For devices which support a code attribute
ATTR_CODE = 'code'
ATTR_CODE_FORMAT = 'code_format'

# For devices which support an armed state
ATTR_ARMED = "device_armed"

# For devices which support a locked state
ATTR_LOCKED = "locked"

# For sensors that support 'tripping', eg. motion and door sensors
ATTR_TRIPPED = "device_tripped"

# For sensors that support 'tripping' this holds the most recent
# time the device was tripped
ATTR_LAST_TRIP_TIME = "last_tripped_time"

# For all entity's, this hold whether or not it should be hidden
ATTR_HIDDEN = "hidden"

# Location of the entity
ATTR_LATITUDE = "latitude"
ATTR_LONGITUDE = "longitude"

# Accuracy of location in meters
ATTR_GPS_ACCURACY = 'gps_accuracy'

# If state is assumed
ATTR_ASSUMED_STATE = 'assumed_state'

# #### SERVICES ####
SERVICE_HOMEASSISTANT_STOP = "stop"
SERVICE_HOMEASSISTANT_RESTART = "restart"

SERVICE_TURN_ON = 'turn_on'
SERVICE_TURN_OFF = 'turn_off'
SERVICE_TOGGLE = 'toggle'

SERVICE_VOLUME_UP = "volume_up"
SERVICE_VOLUME_DOWN = "volume_down"
SERVICE_VOLUME_MUTE = "volume_mute"
SERVICE_VOLUME_SET = "volume_set"
SERVICE_MEDIA_PLAY_PAUSE = "media_play_pause"
SERVICE_MEDIA_PLAY = "media_play"
SERVICE_MEDIA_PAUSE = "media_pause"
SERVICE_MEDIA_STOP = "media_stop"
SERVICE_MEDIA_NEXT_TRACK = "media_next_track"
SERVICE_MEDIA_PREVIOUS_TRACK = "media_previous_track"
SERVICE_MEDIA_SEEK = "media_seek"

SERVICE_ALARM_DISARM = "alarm_disarm"
SERVICE_ALARM_ARM_HOME = "alarm_arm_home"
SERVICE_ALARM_ARM_AWAY = "alarm_arm_away"
SERVICE_ALARM_TRIGGER = "alarm_trigger"

SERVICE_LOCK = "lock"
SERVICE_UNLOCK = "unlock"

SERVICE_OPEN = "open"
SERVICE_CLOSE = "close"

SERVICE_MOVE_UP = 'move_up'
SERVICE_MOVE_DOWN = 'move_down'
SERVICE_STOP = 'stop'

# #### API / REMOTE ####
SERVER_PORT = 8123

URL_ROOT = "/"
URL_API = "/api/"
URL_API_STREAM = "/api/stream"
URL_API_CONFIG = "/api/config"
URL_API_DISCOVERY_INFO = "/api/discovery_info"
URL_API_STATES = "/api/states"
URL_API_STATES_ENTITY = "/api/states/{}"
URL_API_EVENTS = "/api/events"
URL_API_EVENTS_EVENT = "/api/events/{}"
URL_API_SERVICES = "/api/services"
URL_API_SERVICES_SERVICE = "/api/services/{}/{}"
URL_API_EVENT_FORWARD = "/api/event_forwarding"
URL_API_COMPONENTS = "/api/components"
URL_API_ERROR_LOG = "/api/error_log"
URL_API_LOG_OUT = "/api/log_out"
URL_API_TEMPLATE = "/api/template"

HTTP_OK = 200
HTTP_CREATED = 201
HTTP_MOVED_PERMANENTLY = 301
HTTP_BAD_REQUEST = 400
HTTP_UNAUTHORIZED = 401
HTTP_NOT_FOUND = 404
HTTP_METHOD_NOT_ALLOWED = 405
HTTP_UNPROCESSABLE_ENTITY = 422
HTTP_INTERNAL_SERVER_ERROR = 500

HTTP_HEADER_HA_AUTH = "X-HA-access"
HTTP_HEADER_ACCEPT_ENCODING = "Accept-Encoding"
HTTP_HEADER_CONTENT_TYPE = "Content-type"
HTTP_HEADER_CONTENT_ENCODING = "Content-Encoding"
HTTP_HEADER_VARY = "Vary"
HTTP_HEADER_CONTENT_LENGTH = "Content-Length"
HTTP_HEADER_CACHE_CONTROL = "Cache-Control"
HTTP_HEADER_EXPIRES = "Expires"
HTTP_HEADER_ORIGIN = "Origin"
HTTP_HEADER_X_REQUESTED_WITH = "X-Requested-With"
HTTP_HEADER_ACCEPT = "Accept"
HTTP_HEADER_ACCESS_CONTROL_ALLOW_ORIGIN = "Access-Control-Allow-Origin"
HTTP_HEADER_ACCESS_CONTROL_ALLOW_HEADERS = "Access-Control-Allow-Headers"

ALLOWED_CORS_HEADERS = [HTTP_HEADER_ORIGIN, HTTP_HEADER_ACCEPT,
                        HTTP_HEADER_X_REQUESTED_WITH, HTTP_HEADER_CONTENT_TYPE,
                        HTTP_HEADER_HA_AUTH]

CONTENT_TYPE_JSON = "application/json"
CONTENT_TYPE_MULTIPART = 'multipart/x-mixed-replace; boundary={}'
CONTENT_TYPE_TEXT_PLAIN = 'text/plain'

# The exit code to send to request a restart
RESTART_EXIT_CODE = 100
