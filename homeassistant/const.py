""" Constants used by Home Assistant components. """
# Can be used to specify a catch all when registering state or event listeners.
MATCH_ALL = '*'

# If no name is specified
DEVICE_DEFAULT_NAME = "Unnamed Device"

# #### CONFIG ####
CONF_LATITUDE = "latitude"
CONF_LONGITUDE = "longitude"
CONF_TEMPERATURE_UNIT = "temperature_unit"
CONF_NAME = "name"
CONF_TIME_ZONE = "time_zone"
CONF_CUSTOMIZE = "customize"

CONF_PLATFORM = "platform"
CONF_HOST = "host"
CONF_HOSTS = "hosts"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_API_KEY = "api_key"
CONF_ACCESS_TOKEN = "access_token"

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
STATE_UNKNOWN = "unknown"
STATE_OPEN = 'open'
STATE_CLOSED = 'closed'

# #### STATE AND EVENT ATTRIBUTES ####
# Contains current time for a TIME_CHANGED event
ATTR_NOW = "now"

# Contains domain, service for a SERVICE_CALL event
ATTR_DOMAIN = "domain"
ATTR_SERVICE = "service"

# Data for a SERVICE_EXECUTED event
ATTR_SERVICE_CALL_ID = "service_call_id"

# Contains one string or a list of strings, each being an entity id
ATTR_ENTITY_ID = 'entity_id'

# String with a friendly name for the entity
ATTR_FRIENDLY_NAME = "friendly_name"

# A picture to represent entity
ATTR_ENTITY_PICTURE = "entity_picture"

# The unit of measurement if applicable
ATTR_UNIT_OF_MEASUREMENT = "unit_of_measurement"

# Temperature attribute
ATTR_TEMPERATURE = "temperature"
TEMP_CELCIUS = "°C"
TEMP_FAHRENHEIT = "°F"

# Contains the information that is discovered
ATTR_DISCOVERED = "discovered"

# Location of the device/sensor
ATTR_LOCATION = "location"

ATTR_BATTERY_LEVEL = "battery_level"

# For devices which support an armed state
ATTR_ARMED = "device_armed"

# For sensors that support 'tripping', eg. motion and door sensors
ATTR_TRIPPED = "device_tripped"

# For sensors that support 'tripping' this holds the most recent
# time the device was tripped
ATTR_LAST_TRIP_TIME = "last_tripped_time"

# For all entity's, this hold whether or not it should be hidden
ATTR_HIDDEN = "hidden"

# #### SERVICES ####
SERVICE_HOMEASSISTANT_STOP = "stop"

SERVICE_TURN_ON = 'turn_on'
SERVICE_TURN_OFF = 'turn_off'

SERVICE_VOLUME_UP = "volume_up"
SERVICE_VOLUME_DOWN = "volume_down"
SERVICE_VOLUME_MUTE = "volume_mute"
SERVICE_MEDIA_PLAY_PAUSE = "media_play_pause"
SERVICE_MEDIA_PLAY = "media_play"
SERVICE_MEDIA_PAUSE = "media_pause"
SERVICE_MEDIA_NEXT_TRACK = "media_next_track"
SERVICE_MEDIA_PREV_TRACK = "media_prev_track"

# #### API / REMOTE ####
SERVER_PORT = 8123

URL_ROOT = "/"
URL_API = "/api/"
URL_API_STREAM = "/api/stream"
URL_API_STATES = "/api/states"
URL_API_STATES_ENTITY = "/api/states/{}"
URL_API_EVENTS = "/api/events"
URL_API_EVENTS_EVENT = "/api/events/{}"
URL_API_SERVICES = "/api/services"
URL_API_SERVICES_SERVICE = "/api/services/{}/{}"
URL_API_EVENT_FORWARD = "/api/event_forwarding"
URL_API_COMPONENTS = "/api/components"

HTTP_OK = 200
HTTP_CREATED = 201
HTTP_MOVED_PERMANENTLY = 301
HTTP_BAD_REQUEST = 400
HTTP_UNAUTHORIZED = 401
HTTP_NOT_FOUND = 404
HTTP_METHOD_NOT_ALLOWED = 405
HTTP_UNPROCESSABLE_ENTITY = 422

HTTP_HEADER_HA_AUTH = "X-HA-access"
HTTP_HEADER_ACCEPT_ENCODING = "Accept-Encoding"
HTTP_HEADER_CONTENT_TYPE = "Content-type"
HTTP_HEADER_CONTENT_ENCODING = "Content-Encoding"
HTTP_HEADER_VARY = "Vary"
HTTP_HEADER_CONTENT_LENGTH = "Content-Length"
HTTP_HEADER_CACHE_CONTROL = "Cache-Control"
HTTP_HEADER_EXPIRES = "Expires"

CONTENT_TYPE_JSON = "application/json"
