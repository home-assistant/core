"""Constants used by Home Assistant components."""
MAJOR_VERSION = 0
MINOR_VERSION = 108
PATCH_VERSION = "5"
__short_version__ = f"{MAJOR_VERSION}.{MINOR_VERSION}"
__version__ = f"{__short_version__}.{PATCH_VERSION}"
REQUIRED_PYTHON_VER = (3, 7, 0)
# Truthy date string triggers showing related deprecation warning messages.
REQUIRED_NEXT_PYTHON_VER = (3, 8, 0)
REQUIRED_NEXT_PYTHON_DATE = ""

# Format for platform files
PLATFORM_FORMAT = "{platform}.{domain}"

# Can be used to specify a catch all when registering state or event listeners.
MATCH_ALL = "*"

# Entity target all constant
ENTITY_MATCH_NONE = "none"
ENTITY_MATCH_ALL = "all"

# If no name is specified
DEVICE_DEFAULT_NAME = "Unnamed Device"

# Sun events
SUN_EVENT_SUNSET = "sunset"
SUN_EVENT_SUNRISE = "sunrise"

# #### CONFIG ####
CONF_ABOVE = "above"
CONF_ACCESS_TOKEN = "access_token"
CONF_ADDRESS = "address"
CONF_AFTER = "after"
CONF_ALIAS = "alias"
CONF_API_KEY = "api_key"
CONF_API_VERSION = "api_version"
CONF_AT = "at"
CONF_AUTH_MFA_MODULES = "auth_mfa_modules"
CONF_AUTH_PROVIDERS = "auth_providers"
CONF_AUTHENTICATION = "authentication"
CONF_BASE = "base"
CONF_BEFORE = "before"
CONF_BELOW = "below"
CONF_BINARY_SENSORS = "binary_sensors"
CONF_BLACKLIST = "blacklist"
CONF_BRIGHTNESS = "brightness"
CONF_BROADCAST_ADDRESS = "broadcast_address"
CONF_CLIENT_ID = "client_id"
CONF_CLIENT_SECRET = "client_secret"
CONF_CODE = "code"
CONF_COLOR_TEMP = "color_temp"
CONF_COMMAND = "command"
CONF_COMMAND_CLOSE = "command_close"
CONF_COMMAND_OFF = "command_off"
CONF_COMMAND_ON = "command_on"
CONF_COMMAND_OPEN = "command_open"
CONF_COMMAND_STATE = "command_state"
CONF_COMMAND_STOP = "command_stop"
CONF_CONDITION = "condition"
CONF_CONTINUE_ON_TIMEOUT = "continue_on_timeout"
CONF_COVERS = "covers"
CONF_CURRENCY = "currency"
CONF_CUSTOMIZE = "customize"
CONF_CUSTOMIZE_DOMAIN = "customize_domain"
CONF_CUSTOMIZE_GLOB = "customize_glob"
CONF_DELAY = "delay"
CONF_DELAY_TIME = "delay_time"
CONF_DEVICE = "device"
CONF_DEVICE_CLASS = "device_class"
CONF_DEVICE_ID = "device_id"
CONF_DEVICES = "devices"
CONF_DISARM_AFTER_TRIGGER = "disarm_after_trigger"
CONF_DISCOVERY = "discovery"
CONF_DISKS = "disks"
CONF_DISPLAY_CURRENCY = "display_currency"
CONF_DISPLAY_OPTIONS = "display_options"
CONF_DOMAIN = "domain"
CONF_DOMAINS = "domains"
CONF_EFFECT = "effect"
CONF_ELEVATION = "elevation"
CONF_EMAIL = "email"
CONF_ENTITIES = "entities"
CONF_ENTITY_ID = "entity_id"
CONF_ENTITY_NAMESPACE = "entity_namespace"
CONF_ENTITY_PICTURE_TEMPLATE = "entity_picture_template"
CONF_EVENT = "event"
CONF_EVENT_DATA = "event_data"
CONF_EVENT_DATA_TEMPLATE = "event_data_template"
CONF_EXCLUDE = "exclude"
CONF_FILE_PATH = "file_path"
CONF_FILENAME = "filename"
CONF_FOR = "for"
CONF_FORCE_UPDATE = "force_update"
CONF_FRIENDLY_NAME = "friendly_name"
CONF_FRIENDLY_NAME_TEMPLATE = "friendly_name_template"
CONF_HEADERS = "headers"
CONF_HOST = "host"
CONF_HOSTS = "hosts"
CONF_HS = "hs"
CONF_ICON = "icon"
CONF_ICON_TEMPLATE = "icon_template"
CONF_ID = "id"
CONF_INCLUDE = "include"
CONF_IP_ADDRESS = "ip_address"
CONF_LATITUDE = "latitude"
CONF_LIGHTS = "lights"
CONF_LONGITUDE = "longitude"
CONF_MAC = "mac"
CONF_MAXIMUM = "maximum"
CONF_METHOD = "method"
CONF_MINIMUM = "minimum"
CONF_MODE = "mode"
CONF_MONITORED_CONDITIONS = "monitored_conditions"
CONF_MONITORED_VARIABLES = "monitored_variables"
CONF_NAME = "name"
CONF_OFFSET = "offset"
CONF_OPTIMISTIC = "optimistic"
CONF_PACKAGES = "packages"
CONF_PASSWORD = "password"
CONF_PATH = "path"
CONF_PAYLOAD = "payload"
CONF_PAYLOAD_OFF = "payload_off"
CONF_PAYLOAD_ON = "payload_on"
CONF_PENDING_TIME = "pending_time"
CONF_PIN = "pin"
CONF_PLATFORM = "platform"
CONF_PORT = "port"
CONF_PREFIX = "prefix"
CONF_PROFILE_NAME = "profile_name"
CONF_PROTOCOL = "protocol"
CONF_PROXY_SSL = "proxy_ssl"
CONF_QUOTE = "quote"
CONF_RADIUS = "radius"
CONF_RECIPIENT = "recipient"
CONF_REGION = "region"
CONF_RESOURCE = "resource"
CONF_RESOURCE_TEMPLATE = "resource_template"
CONF_RESOURCES = "resources"
CONF_RGB = "rgb"
CONF_ROOM = "room"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_SCENE = "scene"
CONF_SENDER = "sender"
CONF_SENSOR_TYPE = "sensor_type"
CONF_SENSORS = "sensors"
CONF_SERVICE = "service"
CONF_SERVICE_DATA = "data"
CONF_SERVICE_TEMPLATE = "service_template"
CONF_SHOW_ON_MAP = "show_on_map"
CONF_SLAVE = "slave"
CONF_SOURCE = "source"
CONF_SSL = "ssl"
CONF_STATE = "state"
CONF_STATE_TEMPLATE = "state_template"
CONF_STRUCTURE = "structure"
CONF_SWITCHES = "switches"
CONF_TEMPERATURE_UNIT = "temperature_unit"
CONF_TIME_ZONE = "time_zone"
CONF_TIMEOUT = "timeout"
CONF_TOKEN = "token"
CONF_TRIGGER_TIME = "trigger_time"
CONF_TTL = "ttl"
CONF_TYPE = "type"
CONF_UNIT_OF_MEASUREMENT = "unit_of_measurement"
CONF_UNIT_SYSTEM = "unit_system"
CONF_URL = "url"
CONF_USERNAME = "username"
CONF_VALUE_TEMPLATE = "value_template"
CONF_VERIFY_SSL = "verify_ssl"
CONF_WAIT_TEMPLATE = "wait_template"
CONF_WEBHOOK_ID = "webhook_id"
CONF_WEEKDAY = "weekday"
CONF_WHITE_VALUE = "white_value"
CONF_WHITELIST = "whitelist"
CONF_WHITELIST_EXTERNAL_DIRS = "whitelist_external_dirs"
CONF_XY = "xy"
CONF_ZONE = "zone"

# #### EVENTS ####
EVENT_AUTOMATION_TRIGGERED = "automation_triggered"
EVENT_CALL_SERVICE = "call_service"
EVENT_COMPONENT_LOADED = "component_loaded"
EVENT_CORE_CONFIG_UPDATE = "core_config_updated"
EVENT_HOMEASSISTANT_CLOSE = "homeassistant_close"
EVENT_HOMEASSISTANT_START = "homeassistant_start"
EVENT_HOMEASSISTANT_STOP = "homeassistant_stop"
EVENT_HOMEASSISTANT_FINAL_WRITE = "homeassistant_final_write"
EVENT_LOGBOOK_ENTRY = "logbook_entry"
EVENT_PLATFORM_DISCOVERED = "platform_discovered"
EVENT_SCRIPT_STARTED = "script_started"
EVENT_SERVICE_REGISTERED = "service_registered"
EVENT_SERVICE_REMOVED = "service_removed"
EVENT_STATE_CHANGED = "state_changed"
EVENT_THEMES_UPDATED = "themes_updated"
EVENT_TIMER_OUT_OF_SYNC = "timer_out_of_sync"
EVENT_TIME_CHANGED = "time_changed"


# #### DEVICE CLASSES ####
DEVICE_CLASS_BATTERY = "battery"
DEVICE_CLASS_HUMIDITY = "humidity"
DEVICE_CLASS_ILLUMINANCE = "illuminance"
DEVICE_CLASS_SIGNAL_STRENGTH = "signal_strength"
DEVICE_CLASS_TEMPERATURE = "temperature"
DEVICE_CLASS_TIMESTAMP = "timestamp"
DEVICE_CLASS_PRESSURE = "pressure"
DEVICE_CLASS_POWER = "power"

# #### STATES ####
STATE_ON = "on"
STATE_OFF = "off"
STATE_HOME = "home"
STATE_NOT_HOME = "not_home"
STATE_UNKNOWN = "unknown"
STATE_OPEN = "open"
STATE_OPENING = "opening"
STATE_CLOSED = "closed"
STATE_CLOSING = "closing"
STATE_PLAYING = "playing"
STATE_PAUSED = "paused"
STATE_IDLE = "idle"
STATE_STANDBY = "standby"
STATE_ALARM_DISARMED = "disarmed"
STATE_ALARM_ARMED_HOME = "armed_home"
STATE_ALARM_ARMED_AWAY = "armed_away"
STATE_ALARM_ARMED_NIGHT = "armed_night"
STATE_ALARM_ARMED_CUSTOM_BYPASS = "armed_custom_bypass"
STATE_ALARM_PENDING = "pending"
STATE_ALARM_ARMING = "arming"
STATE_ALARM_DISARMING = "disarming"
STATE_ALARM_TRIGGERED = "triggered"
STATE_LOCKED = "locked"
STATE_UNLOCKED = "unlocked"
STATE_UNAVAILABLE = "unavailable"
STATE_OK = "ok"
STATE_PROBLEM = "problem"

# #### STATE AND EVENT ATTRIBUTES ####
# Attribution
ATTR_ATTRIBUTION = "attribution"

# Credentials
ATTR_CREDENTIALS = "credentials"

# Contains time-related attributes
ATTR_NOW = "now"
ATTR_DATE = "date"
ATTR_TIME = "time"
ATTR_SECONDS = "seconds"

# Contains domain, service for a SERVICE_CALL event
ATTR_DOMAIN = "domain"
ATTR_SERVICE = "service"
ATTR_SERVICE_DATA = "service_data"

# IDs
ATTR_ID = "id"

# Name
ATTR_NAME = "name"

# Contains one string or a list of strings, each being an entity id
ATTR_ENTITY_ID = "entity_id"

# Contains one string or a list of strings, each being an area id
ATTR_AREA_ID = "area_id"

# String with a friendly name for the entity
ATTR_FRIENDLY_NAME = "friendly_name"

# A picture to represent entity
ATTR_ENTITY_PICTURE = "entity_picture"

# Icon to use in the frontend
ATTR_ICON = "icon"

# The unit of measurement if applicable
ATTR_UNIT_OF_MEASUREMENT = "unit_of_measurement"

CONF_UNIT_SYSTEM_METRIC: str = "metric"
CONF_UNIT_SYSTEM_IMPERIAL: str = "imperial"

# Electrical attributes
ATTR_VOLTAGE = "voltage"

# Contains the information that is discovered
ATTR_DISCOVERED = "discovered"

# Location of the device/sensor
ATTR_LOCATION = "location"

ATTR_MODE = "mode"

ATTR_BATTERY_CHARGING = "battery_charging"
ATTR_BATTERY_LEVEL = "battery_level"
ATTR_WAKEUP = "wake_up_interval"

# For devices which support a code attribute
ATTR_CODE = "code"
ATTR_CODE_FORMAT = "code_format"

# For calling a device specific command
ATTR_COMMAND = "command"

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
ATTR_GPS_ACCURACY = "gps_accuracy"

# If state is assumed
ATTR_ASSUMED_STATE = "assumed_state"
ATTR_STATE = "state"

ATTR_EDITABLE = "editable"
ATTR_OPTION = "option"

# Bitfield of supported component features for the entity
ATTR_SUPPORTED_FEATURES = "supported_features"

# Class of device within its domain
ATTR_DEVICE_CLASS = "device_class"

# Temperature attribute
ATTR_TEMPERATURE = "temperature"

# #### UNITS OF MEASUREMENT ####
# Power units
POWER_WATT = "W"

# Energy units
ENERGY_KILO_WATT_HOUR = "kWh"
ENERGY_WATT_HOUR = "Wh"

# Temperature units
TEMP_CELSIUS = "°C"
TEMP_FAHRENHEIT = "°F"

# Time units
TIME_MICROSECONDS = "μs"
TIME_MILLISECONDS = "ms"
TIME_SECONDS = "s"
TIME_MINUTES = "min"
TIME_HOURS = "h"
TIME_DAYS = "d"
TIME_WEEKS = "w"
TIME_MONTHS = "m"
TIME_YEARS = "y"

# Length units
LENGTH_CENTIMETERS: str = "cm"
LENGTH_METERS: str = "m"
LENGTH_KILOMETERS: str = "km"

LENGTH_INCHES: str = "in"
LENGTH_FEET: str = "ft"
LENGTH_YARD: str = "yd"
LENGTH_MILES: str = "mi"

# Pressure units
PRESSURE_PA: str = "Pa"
PRESSURE_HPA: str = "hPa"
PRESSURE_BAR: str = "bar"
PRESSURE_MBAR: str = "mbar"
PRESSURE_INHG: str = "inHg"
PRESSURE_PSI: str = "psi"

# Volume units
VOLUME_LITERS: str = "L"
VOLUME_MILLILITERS: str = "mL"
VOLUME_CUBIC_METERS = f"{LENGTH_METERS}³"

VOLUME_GALLONS: str = "gal"
VOLUME_FLUID_OUNCE: str = "fl. oz."

# Area units
AREA_SQUARE_METERS = f"{LENGTH_METERS}²"

# Mass units
MASS_GRAMS: str = "g"
MASS_KILOGRAMS: str = "kg"
MASS_MILLIGRAMS = "mg"
MASS_MICROGRAMS = "µg"

MASS_OUNCES: str = "oz"
MASS_POUNDS: str = "lb"

# UV Index units
UNIT_UV_INDEX: str = "UV index"

# Percentage units
UNIT_PERCENTAGE = "%"
# Irradiation units
IRRADIATION_WATTS_PER_SQUARE_METER = f"{POWER_WATT}/{AREA_SQUARE_METERS}"

# Concentration units
CONCENTRATION_MICROGRAMS_PER_CUBIC_METER = f"{MASS_MICROGRAMS}/{VOLUME_CUBIC_METERS}"
CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER = f"{MASS_MILLIGRAMS}/{VOLUME_CUBIC_METERS}"
CONCENTRATION_PARTS_PER_MILLION = "ppm"
CONCENTRATION_PARTS_PER_BILLION = "ppb"

# Speed units
SPEED_METERS_PER_SECOND = f"{LENGTH_METERS}/{TIME_SECONDS}"
SPEED_KILOMETERS_PER_HOUR = f"{LENGTH_KILOMETERS}/{TIME_HOURS}"
SPEED_MILES_PER_HOUR = "mph"

# Data units
DATA_BITS = "bit"
DATA_KILOBITS = "kbit"
DATA_MEGABITS = "Mbit"
DATA_GIGABITS = "Gbit"
DATA_BYTES = "B"
DATA_KILOBYTES = "kB"
DATA_MEGABYTES = "MB"
DATA_GIGABYTES = "GB"
DATA_TERABYTES = "TB"
DATA_PETABYTES = "PB"
DATA_EXABYTES = "EB"
DATA_ZETTABYTES = "ZB"
DATA_YOTTABYTES = "YB"
DATA_KIBIBYTES = "KiB"
DATA_MEBIBYTES = "MiB"
DATA_GIBIBYTES = "GiB"
DATA_TEBIBYTES = "TiB"
DATA_PEBIBYTES = "PiB"
DATA_EXBIBYTES = "EiB"
DATA_ZEBIBYTES = "ZiB"
DATA_YOBIBYTES = "YiB"
DATA_RATE_BITS_PER_SECOND = f"{DATA_BITS}/{TIME_SECONDS}"
DATA_RATE_KILOBITS_PER_SECOND = f"{DATA_KILOBITS}/{TIME_SECONDS}"
DATA_RATE_MEGABITS_PER_SECOND = f"{DATA_MEGABITS}/{TIME_SECONDS}"
DATA_RATE_GIGABITS_PER_SECOND = f"{DATA_GIGABITS}/{TIME_SECONDS}"
DATA_RATE_BYTES_PER_SECOND = f"{DATA_BYTES}/{TIME_SECONDS}"
DATA_RATE_KILOBYTES_PER_SECOND = f"{DATA_KILOBYTES}/{TIME_SECONDS}"
DATA_RATE_MEGABYTES_PER_SECOND = f"{DATA_MEGABYTES}/{TIME_SECONDS}"
DATA_RATE_GIGABYTES_PER_SECOND = f"{DATA_GIGABYTES}/{TIME_SECONDS}"
DATA_RATE_KIBIBYTES_PER_SECOND = f"{DATA_KIBIBYTES}/{TIME_SECONDS}"
DATA_RATE_MEBIBYTES_PER_SECOND = f"{DATA_MEBIBYTES}/{TIME_SECONDS}"
DATA_RATE_GIBIBYTES_PER_SECOND = f"{DATA_GIBIBYTES}/{TIME_SECONDS}"

# #### SERVICES ####
SERVICE_HOMEASSISTANT_STOP = "stop"
SERVICE_HOMEASSISTANT_RESTART = "restart"

SERVICE_TURN_ON = "turn_on"
SERVICE_TURN_OFF = "turn_off"
SERVICE_TOGGLE = "toggle"
SERVICE_RELOAD = "reload"

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
SERVICE_SHUFFLE_SET = "shuffle_set"

SERVICE_ALARM_DISARM = "alarm_disarm"
SERVICE_ALARM_ARM_HOME = "alarm_arm_home"
SERVICE_ALARM_ARM_AWAY = "alarm_arm_away"
SERVICE_ALARM_ARM_NIGHT = "alarm_arm_night"
SERVICE_ALARM_ARM_CUSTOM_BYPASS = "alarm_arm_custom_bypass"
SERVICE_ALARM_TRIGGER = "alarm_trigger"


SERVICE_LOCK = "lock"
SERVICE_UNLOCK = "unlock"

SERVICE_OPEN = "open"
SERVICE_CLOSE = "close"

SERVICE_CLOSE_COVER = "close_cover"
SERVICE_CLOSE_COVER_TILT = "close_cover_tilt"
SERVICE_OPEN_COVER = "open_cover"
SERVICE_OPEN_COVER_TILT = "open_cover_tilt"
SERVICE_SET_COVER_POSITION = "set_cover_position"
SERVICE_SET_COVER_TILT_POSITION = "set_cover_tilt_position"
SERVICE_STOP_COVER = "stop_cover"
SERVICE_STOP_COVER_TILT = "stop_cover_tilt"
SERVICE_TOGGLE_COVER_TILT = "toggle_cover_tilt"

SERVICE_SELECT_OPTION = "select_option"

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
HTTP_TOO_MANY_REQUESTS = 429
HTTP_INTERNAL_SERVER_ERROR = 500
HTTP_SERVICE_UNAVAILABLE = 503

HTTP_BASIC_AUTHENTICATION = "basic"
HTTP_DIGEST_AUTHENTICATION = "digest"

HTTP_HEADER_X_REQUESTED_WITH = "X-Requested-With"

CONTENT_TYPE_JSON = "application/json"
CONTENT_TYPE_MULTIPART = "multipart/x-mixed-replace; boundary={}"
CONTENT_TYPE_TEXT_PLAIN = "text/plain"

# The exit code to send to request a restart
RESTART_EXIT_CODE = 100

UNIT_NOT_RECOGNIZED_TEMPLATE: str = "{} is not a recognized {} unit."

LENGTH: str = "length"
MASS: str = "mass"
PRESSURE: str = "pressure"
VOLUME: str = "volume"
TEMPERATURE: str = "temperature"
SPEED_MS: str = "speed_ms"
ILLUMINANCE: str = "illuminance"

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

# The degree of precision for platforms
PRECISION_WHOLE = 1
PRECISION_HALVES = 0.5
PRECISION_TENTHS = 0.1

# Static list of entities that will never be exposed to
# cloud, alexa, or google_home components
CLOUD_NEVER_EXPOSED_ENTITIES = ["group.all_locks"]
